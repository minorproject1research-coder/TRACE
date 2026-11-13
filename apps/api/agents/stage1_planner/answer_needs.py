"""Sub-questions that a good ANSWER needs and that the fine-tuned planner does not produce.

The planner (LoRA on vLLM) splits a question into background and topic coverage: for "How effective is federated learning compared with centralized
training for medical image analysis, and what are the privacy trade-offs?" it gave "what is X", "what is Y", "how is X applied", the comparison and the
privacy question. Nothing asked WHEN the approach fails (non-IID data, small sites, strict privacy budgets), HOW BIG the gap is, or which attacks and
defences exist, so the report could say "comparable" and "protects privacy" but had nothing on the conditions, the figures or the risks (run 36,
2026-11-13, compared with a deep-research answer to the same question).

This step asks the Groq model (one small call, about 700 tokens) for up to PLAN_ANSWER_SUBQUESTIONS (default 2) extra sub-questions, with search
queries aimed at PRIMARY empirical studies, benchmarks and meta-analyses rather than overviews:
  A. conditions and limits: when does the approach lose its advantage or fail, and by how much;
  B. risks, costs and defences (when the question is about trade-offs, privacy, security, safety, cost, bias, ethics), otherwise
  C. quantitative results: the figures studies report for the question's comparison.
They are appended to the plan. The total stays within MAX_SUBQUESTIONS: when it would be exceeded the DEFINITIONAL background sub-questions that share
the fewest words with the question are left out first ("What is X?" gives a section that cannot answer the question); a sub-question that is not
definitional is only left out when it shares almost nothing with the question.

The result is stored in the plan cache (marker "answer_needs"), so a rerun of the question with PLAN_CACHE=true plans the same way. Any failure leaves
the plan as it was. PLAN_ANSWER_SUBQUESTIONS=0 switches the step off.
"""
import json
import logging
import os
import re

logger = logging.getLogger("apps.api.agents.stage1_planner")

DEFAULT_ADD = 2
MAX_QUERIES_EACH = 3
_DEFINITIONAL = re.compile(r"^\s*(what\s+(is|are|was|were)\b|define\b|how\s+does\s+.+\s+work\b|overview\b|background\b|history\b|introduction\b)", re.I)
_LABEL = re.compile(r"^\s*(?:[ABC][.):]\s+)?(?:conditions and limits|risks,? costs and defen[cs]es|quantitative results)\s*[:\-–—]\s*", re.I)
_STOP = frozenset("a an and are as at be by can could do does for from has have how in into is it its of on or than that the their there these this to was were what when "
                  "which who why will with would about across between compared compare versus vs other over under using use used based".split())

PROMPT = """You are a research planner. A first planner already split the research question into the sub-questions listed below, mostly background and topic coverage. Write exactly {n} NEW sub-questions, in this order, that a good answer to the research question needs and that are missing (the first is always A; the second is B, or C when B does not apply; a third, if asked for, is the other of B and C):
 A. Conditions and limits: when does the approach or claim in the question fall short, fail or lose its advantage (which conditions), and how large is the difference, according to empirical evidence?
 B. Risks, costs and defences: only when the question is about trade-offs, risks, privacy, security, safety, cost, bias or ethics: which risks or attacks are documented, which countermeasures reduce them, and what do those countermeasures cost?
 If B does not apply, use instead C. Quantitative results: which figures (effect sizes, accuracy, error, cost) do studies report for the comparison in the question?
Write each as a question about the subject of the research question, in its own terms, with 2 or 3 detail questions. Then write 2 or 3 short search queries per new sub-question, in the terms researchers use, aimed at PRIMARY empirical studies, benchmarks, trials, and meta-analyses or systematic reviews that report results (use words like "benchmark", "empirical evaluation", "meta-analysis", "comparison" where they fit), not overviews or introductions.
Do not repeat an existing sub-question. Use only terms from the question and common technical terms of its field; do not invent names of papers, methods or numbers.

Research question: {question}

Existing sub-questions:
{existing}

Return ONLY a JSON object in exactly this format:
{{"sub_questions": [{{"topic": "...", "details": ["...", "..."]}}], "search_queries": ["...", "..."]}}
"""


def count() -> int:
    try:
        return max(0, min(3, int(os.getenv("PLAN_ANSWER_SUBQUESTIONS", str(DEFAULT_ADD)))))
    except ValueError:
        return DEFAULT_ADD


def _tokens(text: str) -> set:
    t = re.sub(r"[‐-―−]", "-", (text or "").lower())
    out = set()
    for w in re.findall(r"[a-z][a-z0-9\-]+", t):
        for x in [w] + ([p for p in w.split("-") if p] if "-" in w else []):
            if x not in _STOP and len(x) > 2:
                out.add(x[:-1] if x.endswith("s") and len(x) > 4 else x)
    return out


def _overlap(topic: str, question_tokens: set) -> float:
    t = _tokens(topic)
    return len(t & question_tokens) / len(t) if t else 0.0


def _similar(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.7


def _parse(raw: str) -> dict:
    text = (raw or "").strip().replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])


def _validated(obj: dict, existing_topics: list, n: int) -> tuple:
    """(new sub-questions [{"topic","details"}], new queries) from a parsed reply: shape-checked, de-duplicated against the existing topics, at most n."""
    new, seen = [], list(existing_topics)
    for s in (obj.get("sub_questions") or []) if isinstance(obj, dict) else []:
        if not isinstance(s, dict):
            continue
        topic = _LABEL.sub("", " ".join(str(s.get("topic") or "").split()))[:220]       # the model sometimes copies the label of the kind ("Conditions and limits: ...")
        if len(topic) < 15 or any(_similar(topic, o) for o in seen):
            continue
        details = [" ".join(str(d).split())[:220] for d in (s.get("details") or []) if str(d).strip()][:3]
        new.append({"topic": topic, "details": details or [topic]})
        seen.append(topic)
        if len(new) >= n:
            break
    queries = [" ".join(str(q).split())[:160] for q in (obj.get("search_queries") or []) if str(q).strip()] if isinstance(obj, dict) else []
    return new, list(dict.fromkeys(queries))[:MAX_QUERIES_EACH * max(len(new), 1)]


def _drop_for_room(sub_questions: list, question: str, excess: int) -> list:
    """The indexes of existing sub-questions to leave out so that `excess` new ones fit: definitional ones with the least overlap with the question first;
    a non-definitional one only when it shares almost nothing with the question (overlap < 0.35). May return fewer than `excess`."""
    q = _tokens(question)
    ranked = sorted(range(len(sub_questions)), key=lambda i: (0 if _DEFINITIONAL.match(sub_questions[i]["topic"]) else 1, _overlap(sub_questions[i]["topic"], q)))
    drop = []
    for i in ranked:
        if len(drop) >= excess:
            break
        if _DEFINITIONAL.match(sub_questions[i]["topic"]) or _overlap(sub_questions[i]["topic"], q) < 0.35:
            drop.append(i)
    return drop


def augment(question: str, plan: dict, cap: int, chat=None) -> tuple:
    """(plan, info). `plan` is the planner's {"sub_questions", "search_queries"}; `info` = {"added": [topics], "dropped": [topics]} (also for a plan that already
    carries the marker), or None when nothing was done (switched off, failure, nothing to add). Never raises; the plan is changed in place."""
    n = count()
    if n == 0 or not isinstance(plan, dict) or not plan.get("sub_questions"):
        return plan, None
    marker = plan.get("answer_needs")
    if isinstance(marker, dict):
        return plan, {"added": list(marker.get("added") or []), "dropped": list(marker.get("dropped") or []), "stored": True}
    try:
        existing = [s["topic"] for s in plan["sub_questions"]]
        prompt = PROMPT.format(n=n, question=question, existing="\n".join(f"- {t}" for t in existing))
        if chat is None:
            from apps.api.services import groq_pool
            response = groq_pool.chat(messages=[{"role": "user", "content": prompt}], model="openai/gpt-oss-120b", temperature=0.1, purpose="planner_answer_needs")
            raw = response.choices[0].message.content
        else:
            raw = chat(prompt)
        new, queries = _validated(_parse(raw), existing, n)
        if not new:
            logger.info("Planner answer-needs step: nothing new to add")
            return plan, None
        room = max(0, cap - len(plan["sub_questions"]))
        dropped_idx: list = []
        if len(new) > room:
            dropped_idx = _drop_for_room(plan["sub_questions"], question, len(new) - room)
            room += len(dropped_idx)
        new = new[:room]
        if not new:
            return plan, None
        dropped = [plan["sub_questions"][i]["topic"] for i in dropped_idx]
        kept = [s for i, s in enumerate(plan["sub_questions"]) if i not in set(dropped_idx)]
        plan["sub_questions"] = kept + new
        plan["search_queries"] = list(plan.get("search_queries") or []) + queries
        info = {"added": [s["topic"] for s in new], "dropped": dropped}
        plan["answer_needs"] = dict(info)
        logger.info("Planner answer-needs step: added %s, left out %s", info["added"], dropped)
        return plan, info
    except Exception as e:
        logger.warning("Planner answer-needs step failed (%s: %s); the plan stays as the planner wrote it", type(e).__name__, str(e)[:160])
        return plan, None
