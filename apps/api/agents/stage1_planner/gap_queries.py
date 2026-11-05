# apps/api/agents/stage1_planner/gap_queries.py
"""Loop 2, query step: new search queries for one aspect that Stage 3 found uncovered after judging.

Design (docs/reports/TRACE Stage 3 Coverage Validation Report.md, section 11, step 3 of the escalation ladder):
  1. turn the aspect into a standalone question (an aspect such as "parameters of a transformer" is vague on its own);
  2. ask the planner for alternative plans: one /decompose call with n plans at a raised temperature (decompose_many);
  3. keep only the search queries, interleaved across the plans, with the domain anchor applied as in Stage 1;
  4. drop a query that is too similar (bge cosine >= 0.90) to one already tried or already chosen;
  5. rank what is left by similarity to the standalone question and keep the best few.

Step 5 exists because the planner writes background queries for the whole question ("X definition and overview") next to the targeted
ones; a gap needs the targeted ones, and ranking by similarity to the aspect question needs no threshold.

Only aspects in the state "uncovered after judging" should be passed in; unjudged aspects must never trigger new searches (see
coverage_check). This module only produces queries: running them, parsing, digesting and judging again is the loop's job.
Never raises for a bad planner reply: it returns [] and the caller treats the aspect as a known gap.

  GAP_PLANS=3  GAP_TEMPERATURE=0.8  GAP_MAX_QUERIES=4  GAP_QUERY_DUPLICATE_SIMILARITY=0.90
"""
import logging
import os
import re

from apps.api.agents.stage1_planner import domain_anchor
from apps.api.services import trace_llm_service
from apps.api.services.trace_llm_service import TraceLLMError

logger = logging.getLogger("apps.api.agents.stage1_planner")

GAP_PLANS = int(os.getenv("GAP_PLANS", "3"))
GAP_TEMPERATURE = float(os.getenv("GAP_TEMPERATURE", "0.8"))
GAP_MAX_QUERIES = int(os.getenv("GAP_MAX_QUERIES", "4"))
DUPLICATE_SIMILARITY = float(os.getenv("GAP_QUERY_DUPLICATE_SIMILARITY", "0.90"))
MIN_QUESTION_WORDS = 6          # an aspect that is a question of at least this many words is used as it is


def standalone_question(aspect: str, sub_question: str) -> str:
    """The aspect as a question the planner can decompose without seeing the sub-question."""
    aspect = " ".join(aspect.split())
    topic = " ".join(sub_question.split())
    if aspect.endswith("?") and len(aspect.split()) >= MIN_QUESTION_WORDS:
        return aspect
    aspect = aspect.rstrip("?. ")
    return f"{aspect[:1].upper()}{aspect[1:]} - in the context of the question: {topic}"


def _clean(query) -> str:
    return re.sub(r"\s+", " ", str(query)).strip()


def _interleave(plans: list[dict]) -> list[str]:
    """The first query of every plan, then the second of every plan, and so on (so a duplicate-heavy plan does not crowd out the others)."""
    lists = [[_clean(q) for q in p.get("search_queries", []) if _clean(q)] for p in plans]
    out = []
    for i in range(max((len(l) for l in lists), default=0)):
        out.extend(l[i] for l in lists if i < len(l))
    return out


def generate(aspect: str, sub_question: str, tried_queries: list[str], anchor: str = "", *,
             planner=None, embedder=None, n_plans: int | None = None, temperature: float | None = None,
             max_queries: int | None = None) -> list[str]:
    """New search queries for one uncovered aspect: at most `max_queries`, none a near-duplicate of `tried_queries`.

    anchor: the Stage 1 domain anchor of the original question (TaskPlan.domain_anchor). It is added to the question the planner sees
    ("... (deep learning)") and to every query. Without it "What are the parameters of a transformer?" came back with electrical-transformer
    queries ("turns ratio, impedance, leakage reactance"). The longer domain CONTEXT sentence was tried instead and is worse: it names the
    other topics of the question (SSMs, Mamba) and pulled the planner back to the whole question (0 of 4 queries for that aspect contained
    "parameter", against 4 of 4 with the anchor alone; live check 2026-11-05, one sample per case).
    planner(question, n, temperature) -> list of plans (default: trace_llm_service.decompose_many); embedder: object with
    encode(texts, normalize_embeddings=True) (default: the shared bge model). Both can be replaced in tests."""
    question = standalone_question(aspect, sub_question)
    planner_question = domain_anchor.similarity_text(question, anchor)
    planner = planner or (lambda q, n, t: trace_llm_service.decompose_many(q, n=n, temperature=t))
    try:
        plans = planner(planner_question, n_plans or GAP_PLANS, GAP_TEMPERATURE if temperature is None else temperature)
    except TraceLLMError as e:
        logger.warning("Loop 2: no new queries for '%s' (%s)", aspect[:60], e)
        return []
    candidates = domain_anchor.apply_to_queries(_interleave(plans), anchor)
    limit = max_queries or GAP_MAX_QUERIES
    tried = [_clean(q) for q in tried_queries]

    try:
        if embedder is None:
            from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
            embedder = get_embedder()
        chosen = _drop_near_duplicates(candidates, tried, embedder)
        chosen = _rank_by_question(chosen, question, embedder)
    except Exception as e:                  # never let this break the loop: fall back to exact-duplicate removal, plan order
        logger.warning("Loop 2: similarity step skipped (%s: %s)", type(e).__name__, e)
        seen = {q.lower() for q in tried}
        chosen = []
        for q in candidates:
            if q.lower() not in seen:
                seen.add(q.lower())
                chosen.append(q)
    result = chosen[:limit]
    logger.info("Loop 2: %d plans -> %d candidate queries -> %d new queries for aspect '%s'",
                len(plans), len(candidates), len(result), aspect[:60])
    return result


def _drop_near_duplicates(candidates: list[str], tried: list[str], embedder) -> list[str]:
    if not candidates:
        return []
    known_texts = list(tried)
    known = embedder.encode(known_texts, normalize_embeddings=True) if known_texts else None
    vectors = embedder.encode(candidates, normalize_embeddings=True)
    kept, kept_vectors = [], []
    for query, vec in zip(candidates, vectors):
        if known is not None and float((known @ vec).max()) >= DUPLICATE_SIMILARITY:
            continue
        if any(float(vec @ other) >= DUPLICATE_SIMILARITY for other in kept_vectors):
            continue
        kept.append(query)
        kept_vectors.append(vec)
    return kept


def _rank_by_question(queries: list[str], question: str, embedder) -> list[str]:
    if len(queries) < 2:
        return queries
    q_vec = embedder.encode([question], normalize_embeddings=True)[0]
    vectors = embedder.encode(queries, normalize_embeddings=True)
    order = sorted(range(len(queries)), key=lambda i: -float(vectors[i] @ q_vec))
    return [queries[i] for i in order]
