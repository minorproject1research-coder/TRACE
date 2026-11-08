import logging
import os

from apps.api.agents.stage1_planner import plan_cache
from apps.api.models.task_plan import SubQuestion
from apps.api.services import trace_llm_service
from apps.api.services.trace_llm_service import TraceLLMError

logger = logging.getLogger(__name__)

# Caps keep retrieval time bounded: every search query fans out to arXiv, Semantic Scholar, IEEE, OpenAlex and the web.
MAX_SUBQUESTIONS = int(os.getenv("MAX_SUBQUESTIONS", "5"))
MAX_QUERIES_PER_SUBQUESTION = int(os.getenv("MAX_QUERIES_PER_SUBQUESTION", "3"))
# SUBQUESTION_MERGE: how near-duplicate sub-questions are merged.
#   exact (default)  only sub-questions with the same content words (stop words, case and a plural "s" ignored)
#   embedding        sub-questions whose topics have bge cosine >= SUBQUESTION_MERGE_SIMILARITY (opt-in, see _merge_similar)
#   off              never
MERGE_SIMILARITY = float(os.getenv("SUBQUESTION_MERGE_SIMILARITY", "0.97"))     # only used in "embedding" mode
# A query whose similarity to the sub-question it was handed to is below this is dropped (0 = keep every query). The even-share hand-out
# below can force a query onto a sub-question it does not fit: in the Q2 run (MoE) "large language model training and usage" and "mixture of
# experts in large language models benefits and challenges" went to "How is MoE applied to LLMs?" at similarity 0.54 (the full sub-question
# "What is a large language model?" fitted them at 0.76 and 0.70), and that sub-question's web results were three generic LLM pages with no
# findings. Over all 447 queries stored in the database 11 were below 0.55 (2%) and 9 of those fitted another sub-question >= 0.10 better.
# A sub-question left without queries is expanded by planner_node (query_expansion). 0.55 is a judgement from that distribution.
MIN_ASSIGN_SIMILARITY = float(os.getenv("QUERY_MIN_SIMILARITY", "0.55"))
MAX_DETAIL_QUESTIONS = int(os.getenv("MAX_DETAIL_QUESTIONS", "5"))      # detail questions kept after a merge
DETAIL_DUPLICATE_SIMILARITY = 0.9                                       # a merged-in detail this close to one we have is dropped
# groq: if the model server is unreachable, decompose with the Groq model instead; none: raise the error
LLM_FALLBACK = os.getenv("TRACE_LLM_FALLBACK", "groq").lower()


def generate(raw_query: str) -> list[SubQuestion]:
    """Break a research question into sub-questions using the fine-tuned planner (POST /decompose).

    The planner also returns search queries, as one flat list for the whole question. They are split across the
    sub-questions here (sq.queries); any sub-question left without a query is filled by query_expansion afterwards."""
    logger.info("Generating sub-questions for query: %s", raw_query[:100])
    plan = plan_cache.load(raw_query)                   # opt-in (PLAN_CACHE=true): the planner is not reproducible, see plan_cache
    if plan is not None:
        source = "plan-cache"
    else:
        try:
            plan = trace_llm_service.decompose(raw_query)
            source = "planner"
            plan_cache.store(raw_query, plan)
        except TraceLLMError as e:
            if LLM_FALLBACK != "groq":
                raise
            logger.warning("Planner server unavailable (%s); falling back to Groq decomposition", e)
            plan = _groq_decompose(raw_query)
            source = "groq-fallback"

    sub_questions = _build_sub_questions(plan)
    _assign_queries(sub_questions, plan["search_queries"])
    logger.info("Planner (%s): %d sub-questions, %d search queries -> %s", source, len(sub_questions),
                len(plan["search_queries"]), [len(sq.queries) for sq in sub_questions])
    return sub_questions


def _merge_mode() -> str:
    mode = os.getenv("SUBQUESTION_MERGE", "exact").strip().lower()
    return mode if mode in ("exact", "embedding", "off") else "exact"


def _absorb_details(host: SubQuestion, other: SubQuestion, model) -> None:
    """Add the detail questions of `other` to `host` (up to MAX_DETAIL_QUESTIONS); one that is almost identical to a known detail is dropped."""
    known = host.detail_questions
    known_vecs = model.encode(known, normalize_embeddings=True)
    for detail in other.detail_questions:
        if len(known) >= MAX_DETAIL_QUESTIONS:
            break
        vec = model.encode([detail], normalize_embeddings=True)[0]
        if float((known_vecs @ vec).max()) < DETAIL_DUPLICATE_SIMILARITY:
            known.append(detail)
            known_vecs = model.encode(known, normalize_embeddings=True)


def _merge_similar(sub_questions: list[SubQuestion]) -> list[SubQuestion]:
    """Merge sub-questions that ask the same thing.

    Default mode "exact": only sub-questions with the same content words are merged. The earlier rule (embedding similarity >= 0.92) merged
    DIFFERENT questions: in the logs 4 of the 5 merges ever made were wrong ("compare in memory cost" into "compare in performance" 0.95,
    twice; "techniques that address the challenges" into "challenges transformers face" 0.95; "compare in long-sequence performance" into
    "compare in training efficiency" 0.93) and each one silently removed part of what the user asked. Only one was a true duplicate ("How
    effective is X at reducing Y?" into "How does X affect Y?", 0.97). A missed duplicate costs extra search time; a wrong merge costs part of
    the answer, so the default errs on the side of keeping sub-questions apart.

    Mode "embedding" keeps the old rule with SUBQUESTION_MERGE_SIMILARITY (default 0.97, which would have merged only the true duplicate
    above; one example, so treat it as a guess). The first sub-question is kept; the later one's detail questions are added to it."""
    mode = _merge_mode()
    if len(sub_questions) < 2 or mode == "off" or (mode == "embedding" and MERGE_SIMILARITY >= 1.0):
        return sub_questions

    if mode == "exact":
        from apps.api.services.text_norm import normalized_words
        first_with: dict = {}
        kept_list: list[SubQuestion] = []
        for sq in sub_questions:
            key = normalized_words(sq.main_topic)
            host = first_with.get(key)
            if host is None:
                first_with[key] = sq
                kept_list.append(sq)
                continue
            logger.info("Merged identical sub-question '%s' into '%s'", sq.main_topic[:70], host.main_topic[:70])
            try:
                from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
                _absorb_details(host, sq, get_embedder())
            except Exception as e:                      # never let a merge problem break planning
                logger.warning("Detail questions of the merged sub-question were not added (%s: %s)", type(e).__name__, e)
        return kept_list

    try:
        from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder   # shared bge model, loaded once
        model = get_embedder()
        topics = model.encode([sq.main_topic for sq in sub_questions], normalize_embeddings=True)
    except Exception as e:                              # never let a merge problem break planning
        logger.warning("Sub-question merge skipped (%s: %s)", type(e).__name__, e)
        return sub_questions

    kept: list[int] = []                                # indexes into sub_questions
    for i, sq in enumerate(sub_questions):
        target = next((k for k in kept if float(topics[i] @ topics[k]) >= MERGE_SIMILARITY), None)
        if target is None:
            kept.append(i)
            continue
        logger.info("Merged near-duplicate sub-question '%s' into '%s' (similarity %.2f)",
                    sq.main_topic[:70], sub_questions[target].main_topic[:70], float(topics[i] @ topics[target]))
        _absorb_details(sub_questions[target], sq, model)
    return [sub_questions[i] for i in kept]


def _build_sub_questions(plan: dict) -> list[SubQuestion]:
    seen, result = set(), []
    for s in plan["sub_questions"]:
        key = " ".join(s["topic"].lower().split())
        if key in seen:                                 # the planner occasionally repeats a topic
            continue
        seen.add(key)
        result.append(SubQuestion(main_topic=s["topic"], detail_questions=s["details"] or [s["topic"]]))
    result = _merge_similar(result)
    if len(result) > MAX_SUBQUESTIONS:
        logger.warning("Planner returned %d sub-questions; keeping the first %d", len(result), MAX_SUBQUESTIONS)
        result = result[:MAX_SUBQUESTIONS]
    return result


def _assign_queries(sub_questions: list[SubQuestion], queries: list[str]) -> None:
    """Spread the planner's search queries over the sub-questions, balanced.

    Giving every query to the sub-question it matches best (argmax) left the core question with 1 query ([3, 3, 1]), because
    background sub-questions soak up most queries. Instead the (query, sub-question) pairs are taken in order of embedding
    similarity (query against the sub-question's topic and detail questions), and a sub-question stops accepting queries at
    an even share (queries // sub-questions, then the remainder one each, never more than MAX_QUERIES_PER_SUBQUESTION). Every query is used at most once (no
    duplicate searches); with at least as many queries as sub-questions each sub-question gets at least one. Queries beyond
    the total capacity (the least similar ones) are dropped, and so is any query that fits its sub-question worse than MIN_ASSIGN_SIMILARITY."""
    queries = list(dict.fromkeys(queries))              # drop exact duplicates, keep order
    if not queries or not sub_questions:
        return
    from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder   # shared bge model, loaded once

    model = get_embedder()
    sq_vecs = model.encode([f"{sq.main_topic} " + " ".join(sq.detail_questions) for sq in sub_questions],
                           normalize_embeddings=True)
    q_vecs = model.encode(queries, normalize_embeddings=True)
    sims = q_vecs @ sq_vecs.T                           # (queries x sub-questions)

    base, extra = divmod(len(queries), len(sub_questions))
    pairs = sorted(((float(sims[i, j]), i, j) for i in range(len(queries)) for j in range(len(sub_questions))), reverse=True)
    taken: set[int] = set()
    buckets: list[list[tuple[float, str, int]]] = [[] for _ in sub_questions]
    # phase 1: every sub-question up to the even share; phase 2: the remainder, one extra query per sub-question at most
    for capacity in (min(MAX_QUERIES_PER_SUBQUESTION, base), min(MAX_QUERIES_PER_SUBQUESTION, base + 1)):
        for sim, i, j in pairs:
            if i in taken or len(buckets[j]) >= capacity:
                continue
            taken.add(i)
            buckets[j].append((sim, queries[i], i))
    for j, (sq, bucket) in enumerate(zip(sub_questions, buckets)):
        kept = []
        for sim, query, i in sorted(bucket, reverse=True):
            if sim < MIN_ASSIGN_SIMILARITY:
                better = int(sims[i].argmax())
                logger.warning("Dropped query '%s' for sub-question '%s' (similarity %.2f < %.2f); it fits '%s' better (%.2f)",
                               query[:60], sq.main_topic[:50], sim, MIN_ASSIGN_SIMILARITY, sub_questions[better].main_topic[:50], float(sims[i, better]))
                continue
            kept.append(query)
        sq.queries = kept


GROQ_DECOMPOSE_PROMPT = """You are a research planner. Break the research question into 2-5 sub-questions that together cover it
(background concepts first, then the core question), each with 1-3 detail questions, and write short search-ready queries.

Research question: {question}

Return ONLY a JSON object in exactly this format:
{{"sub_questions": [{{"topic": "...", "details": ["...", "..."]}}], "search_queries": ["...", "..."]}}
"""


def _groq_decompose(question: str) -> dict:
    """Fallback with the same output schema as the planner. Used only when the model server is unreachable."""
    from apps.api.services import groq_pool
    response = groq_pool.chat(
        messages=[{"role": "user", "content": GROQ_DECOMPOSE_PROMPT.format(question=question)}],
        model="openai/gpt-oss-120b", temperature=0.3, purpose="planner_fallback",
    )
    raw = response.choices[0].message.content.strip()
    obj = trace_llm_service.extract_json_from_output(raw.replace("```json", "").replace("```", ""))
    try:
        return trace_llm_service._normalize_plan(obj)
    except TraceLLMError as e:
        raise TraceLLMError(f"Groq fallback also failed: {e}") from e
