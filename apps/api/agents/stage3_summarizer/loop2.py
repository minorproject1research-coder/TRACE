# apps/api/agents/stage3_summarizer/loop2.py
"""Loop 2: search again for the aspects that Stage 3 judged but could not cover.

Design: docs/reports/TRACE Stage 3 Coverage Validation Report.md section 11; plan and pass rules: docs/KNOWN_LIMITS.md items A1 to A6.
It runs inside the summarizer node, after the judge and the coverage check of a sub-question and BEFORE anything is stored, so the stored
digests and coverage are the final ones (the API and the report read the newest generation per sub-question and need no change).

For every uncovered aspect that passes the triage, a ladder of ever more expensive steps is tried, cheapest first; the ladder stops for an
aspect as soon as it is covered:
  reselect   chunks of the papers already parsed that the digest has not read, chosen for the aspect (no download, no parsing)
  pool       the next-ranked papers of the Stage 2 pool of this sub-question: parse, read the best passages for the aspect
  queries    new search queries for the aspect (gap_queries), papers and web pages: retrieve, filter, store, parse, read
After a step that added sources the whole sub-question is judged again (the verdict cache makes that cost only the new pairs) and
coverage is recomputed with the same rule as before: 2 "yes" from 2 sources.

Triage (A1, report 16): an aspect is searched again if its judged candidates hold at least LOOP2_MIN_SIGNAL "yes" or "partial" verdicts
(it has evidence on the topic), or if it had no candidates at all. Aspects with only "no" verdicts are the planner's inventions as a rule
(Q3 diversity, security, interoperability; Q5 scaling) and are recorded as known gaps without spending a search. The rule agreed with a
hand label in 79% of 29 cases (bar 80%), so it is a default, not a validated rule; LOOP2_TRIAGE=all searches every uncovered aspect (used
to measure the yield of the skipped ones).

Stop rules (A3): at most LOOP2_MAX_ROUNDS steps per aspect, at most LOOP2_MAX_ASPECTS aspects per sub-question, a time budget for the
whole loop, and an aspect that is judged "unjudged" (a verdict failed) is never searched. What is still uncovered at the end is a KNOWN
GAP; the state of every aspect is stored in coverage judge_stats["loop2"] (no migration).

  LOOP2=false                 switch (default off)
  LOOP2_STEPS=reselect,pool,queries
  LOOP2_MAX_ROUNDS=3          steps per aspect
  LOOP2_TRIAGE=r1|all         r1
  LOOP2_MIN_SIGNAL=2
  LOOP2_MAX_ASPECTS=4         aspects searched per sub-question
  LOOP2_CHUNKS_PER_ASPECT=2   chunks per aspect and paper
  LOOP2_POOL_PAPERS=3         pool papers parsed per sub-question
  LOOP2_NEW_PAPERS=3          papers kept from the new queries per sub-question
  LOOP2_NEW_WEB=3             web pages kept from the new queries per sub-question
  LOOP2_FOCUS_DIGEST=true     the digest of Loop 2 sees only the aspects being searched
  LOOP2_MAX_SECONDS=1200      budget of the whole loop in one run
"""
import asyncio
import logging
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from apps.api.agents.stage3_summarizer import chunk_selector, coverage_check, digest_generator, evidence_judge

logger = logging.getLogger("apps.api.agents.stage3_summarizer")

STEP_ORDER = ("reselect", "pool", "queries")
MIN_USABLE_TEXT_CHARS = 3000


# ------------------------------------------------------------------------------------------------------------------ settings
def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name, "").strip().lower()
    return default if not v else v in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def enabled() -> bool:
    return _env_bool("LOOP2", False)


def steps() -> list[str]:
    wanted = [s.strip() for s in os.getenv("LOOP2_STEPS", ",".join(STEP_ORDER)).split(",") if s.strip()]
    return [s for s in STEP_ORDER if s in wanted][:max(0, _env_int("LOOP2_MAX_ROUNDS", 3))]


def triage_mode() -> str:
    return "all" if os.getenv("LOOP2_TRIAGE", "r1").strip().lower() == "all" else "r1"


def time_budget() -> float:
    return float(_env_int("LOOP2_MAX_SECONDS", 1200))


# ------------------------------------------------------------------------------------------------------------------ context
@dataclass
class SubQuestionContext:
    query_id: str
    sq: Any                                  # .id .main_topic .queries .detail_questions
    aspects: list[str]                       # exactly the list the judge saw (the topic aspect, if any, is the last one)
    aspect_to_detail: list[int]
    details_for_coverage: list[str]
    digest_aspects: list[str]                # the list the first digest prompt saw
    rows: list[dict]                         # digest rows of this sub-question; Loop 2 appends in place
    chunk_lookup: dict
    papers: list[dict]                       # the papers Stage 3 read, with sections / full_text
    topic_aspect_idx: Optional[int] = None
    anchor: str = ""
    context: str = ""
    web_urls: set = field(default_factory=set)       # web pages already known for this sub-question
    paper_keys: set = field(default_factory=set)     # db_service.paper_key of every paper already kept for this sub-question
    read_chunks: dict = field(default_factory=dict)  # paper id -> chunk ids already given to a digest
    pool_tried: set = field(default_factory=set)
    tried_queries: list = field(default_factory=list)

    @property
    def cleaned_topic(self) -> str:
        return chunk_selector._clean_topic(self.sq.main_topic)


class Services:
    """Everything Loop 2 needs from the outside world, in one place so tests can replace it. Defaults call the real pipeline."""
    can_store = True                         # False (dry run): the queries step does not store its papers and web pages, it only counts them
                                             # (the pool step still parses: that fills the parse cache and changes no run data)

    def __init__(self):
        self._agent = None

    # --- database
    def pool_rows(self, query_id: str, sq_id: str) -> list[dict]:
        from apps.api.services import db_service
        return db_service.supabase.table("retrieved_papers").select("id,title,combined_score,arxiv_id,pdf_url,doi") \
            .eq("query_id", query_id).eq("sub_question_id", sq_id).execute().data

    def papers_by_ids(self, ids: list[str]) -> list[dict]:
        from apps.api.services import db_service
        return db_service.get_papers_by_ids(ids)

    def store_papers(self, query_id: str, papers: list[dict]) -> list[dict]:
        from apps.api.services import db_service
        return db_service.write_retrieved_papers(query_id, papers)

    def store_web(self, sources: list) -> list[dict]:
        from apps.api.services import db_service
        return db_service.write_web_sources(sources)

    # --- retrieval
    def agent(self):
        if self._agent is None:
            from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
            self._agent = PaperRetrievalAgent(max_results_per_query=10)
        return self._agent

    def parse(self, ids: list[str]) -> set:
        """Parse the papers (the agent writes parsed_papers); returns the ids with usable full text."""
        parsed = asyncio.run(self.agent().parse_papers(paper_ids=list(ids)))
        return {p.retrieved_paper_id for p in parsed if len(p.full_text or "") >= MIN_USABLE_TEXT_CHARS}

    def retrieve(self, question: str, queries: list[str]) -> list[dict]:
        return asyncio.run(self.agent().retrieve(sub_question=question, query_variants=queries, enrich=False))

    def relevance(self, question: str, papers: list[dict], anchor: str, context: str) -> list[dict]:
        from apps.api.agents.stage2_retrieval import relevance_filter
        return relevance_filter.filter_relevant(question, papers, anchor=anchor, context=context)

    def score(self, papers: list[dict]) -> list[dict]:
        from apps.api.agents.stage2_retrieval import relevance_filter, reliability_scorer
        return [relevance_filter.compute_combined_score(p) for p in reliability_scorer.score_all(papers)]

    def web(self, queries: list[str]) -> list:
        from apps.api.agents.stage2_retrieval import web_search_agent, reliability_scorer
        return reliability_scorer.score_all(asyncio.run(web_search_agent.search_all(queries)))

    def gap_queries(self, aspect: str, sub_question: str, tried: list[str], anchor: str) -> list[str]:
        from apps.api.agents.stage1_planner import gap_queries
        return gap_queries.generate(aspect, sub_question, tried, anchor)

    def standalone_question(self, aspect: str, sub_question: str) -> str:
        from apps.api.agents.stage1_planner import gap_queries
        return gap_queries.standalone_question(aspect, sub_question)

    # --- Stage 3
    def digest(self, sub_question: str, selected: list, aspects: list[str], main_topic: str, scope: tuple) -> tuple[list[dict], int]:
        return digest_generator.generate_digest_with_retry(sub_question, selected, detail_aspects=aspects, main_topic=main_topic, cache_scope=scope)

    def judge(self, ctx: SubQuestionContext):
        return evidence_judge.run_judge_for_subquestion(ctx.aspects, ctx.rows, ctx.chunk_lookup, topic_aspect_idx=ctx.topic_aspect_idx)

    def paper_key(self, paper: dict) -> str:
        from apps.api.services import db_service
        return db_service.paper_key(paper)

    def digest_workers(self) -> int:
        from apps.api.graph.nodes import summarizer_node
        return summarizer_node._workers()

    def progress(self, message: str, **data) -> None:
        pass


# ------------------------------------------------------------------------------------------------------------------ triage
def verdict_counts(candidates: list[dict], verdicts: dict) -> dict[int, Counter]:
    """{aspect index: Counter of yes / partial / no / error} over the judged candidates."""
    counts: dict[int, Counter] = {}
    for key, entry in (verdicts or {}).items():
        counts.setdefault(key[0], Counter())[coverage_check._verdict_final(entry)] += 1
    return counts


def triage(cov: dict, aspects: list[str], counts: dict[int, Counter]) -> tuple[list[int], dict[int, str]]:
    """(aspect indexes to search again, {aspect index: reason it was not}) among the aspects that are uncovered after judging."""
    reasons_by_text = cov.get("uncovered_reasons") or {}
    min_signal = _env_int("LOOP2_MIN_SIGNAL", 2)
    chosen, skipped = [], {}
    for text in cov.get("uncovered_aspects") or []:
        if text not in aspects:
            continue
        idx = aspects.index(text)
        c = counts.get(idx, Counter())
        if reasons_by_text.get(text) == "no_candidates" or triage_mode() == "all" or c["yes"] + c["partial"] >= min_signal:
            chosen.append(idx)
        else:
            skipped[idx] = "skipped_triage"
    cap = _env_int("LOOP2_MAX_ASPECTS", 4)
    for idx in chosen[cap:]:
        skipped[idx] = "skipped_cap"
    return chosen[:cap], skipped


def _is_covered(cov: dict, text: str) -> bool:
    return text not in (cov.get("uncovered_aspects") or []) and text not in (cov.get("unjudged_aspects") or [])


# ------------------------------------------------------------------------------------------------------------------ digesting new sources
def _digest_specs(ctx: SubQuestionContext, specs: list[dict], open_idx: list[int], svc: Services, step: str) -> list[dict]:
    """Digest rows for new (source, selected chunks) specs. spec = {type, src, selected, weight, level}."""
    if not specs:
        return []
    focus = _env_bool("LOOP2_FOCUS_DIGEST", True)
    aspects_for_prompt = [ctx.aspects[i] for i in open_idx] if focus else ctx.digest_aspects
    main_topic = ctx.cleaned_topic

    def one(spec):
        scope = (str(ctx.sq.id), f"{spec['src']['id']}#loop2-{step}")
        return svc.digest(ctx.sq.main_topic, spec["selected"], aspects_for_prompt, main_topic, scope)

    with ThreadPoolExecutor(max_workers=max(1, svc.digest_workers())) as pool:
        results = list(pool.map(one, specs))

    rows = []
    for spec, (findings, _failures) in zip(specs, results):
        if not findings:
            continue
        for f in findings:
            f["loop2"] = {"step": step}
            if focus:                                    # the prompt numbered only the aspects being searched: back to the judge's numbering
                f["answers_details"] = [{**t, "detail": open_idx[t["detail"] - 1] + 1} for t in f.get("answers_details") or []
                                        if 1 <= t.get("detail", 0) <= len(open_idx)]
        rows.append(digest_generator.digest_row(ctx.query_id, ctx.sq.id, spec["type"], spec["src"], findings, spec["weight"], spec["level"]))
        for cid, text in spec["selected"]:
            ctx.chunk_lookup[f"{spec['src']['id']}:{cid}"] = text
    return rows


def _paper_specs(ctx: SubQuestionContext, papers: list[dict], open_idx: list[int]) -> list[dict]:
    """Chunk selection for papers new to this sub-question: the best passages for the aspects being searched."""
    specs = []
    texts = [ctx.aspects[i] for i in open_idx]
    for p in papers:
        if not p.get("has_full_text"):
            continue
        chunks = chunk_selector.build_chunks(p)
        selected = chunk_selector.select_more_chunks(chunks, texts, set(), _env_int("LOOP2_CHUNKS_PER_ASPECT", 2) + 1, main_topic=ctx.sq.main_topic)
        if selected:
            ctx.read_chunks.setdefault(p["id"], set()).update(i for i, _ in selected)
            specs.append({"type": "paper", "src": p, "selected": selected, "weight": p.get("combined_score"), "level": "full_text"})
    return specs


# ------------------------------------------------------------------------------------------------------------------ the steps
def _step_reselect(ctx, open_idx, svc):
    texts = [ctx.aspects[i] for i in open_idx]
    specs = []
    for p in ctx.papers:
        if not p.get("has_full_text"):
            continue
        chunks = chunk_selector.build_chunks(p)
        if p["id"] not in ctx.read_chunks:
            first = chunk_selector.select_chunks(ctx.sq.main_topic, chunks, detail_questions=ctx.digest_aspects, main_topic=ctx.cleaned_topic)
            ctx.read_chunks[p["id"]] = {i for i, _ in first}
        more = chunk_selector.select_more_chunks(chunks, texts, ctx.read_chunks[p["id"]], _env_int("LOOP2_CHUNKS_PER_ASPECT", 2), main_topic=ctx.sq.main_topic)
        if more:
            ctx.read_chunks[p["id"]].update(i for i, _ in more)
            specs.append({"type": "paper", "src": p, "selected": more, "weight": p.get("combined_score"), "level": "full_text"})
    return _digest_specs(ctx, specs, open_idx, svc, "reselect"), {"sources_tried": len(specs)}


def _step_pool(ctx, open_idx, svc):
    pool = [r for r in svc.pool_rows(ctx.query_id, ctx.sq.id) if r["id"] not in ctx.pool_tried and r["id"] not in {p["id"] for p in ctx.papers}]
    pool.sort(key=lambda r: (bool(r.get("arxiv_id") or r.get("pdf_url")), r.get("combined_score") or 0), reverse=True)
    take = pool[:_env_int("LOOP2_POOL_PAPERS", 3)]
    if not take:
        return [], {"sources_tried": 0, "note": "pool empty"}
    ctx.pool_tried.update(r["id"] for r in take)
    usable = svc.parse([r["id"] for r in take])
    papers = svc.papers_by_ids(sorted(usable))
    ctx.papers.extend(papers)
    return _digest_specs(ctx, _paper_specs(ctx, papers, open_idx), open_idx, svc, "pool"), {"sources_tried": len(take), "parsed": len(usable)}


def _step_queries(ctx, open_idx, svc):
    new_papers: dict[str, dict] = {}
    new_queries: list[str] = []
    web_queries: list[str] = []
    for i in open_idx:
        aspect = ctx.aspects[i]
        queries = svc.gap_queries(aspect, ctx.sq.main_topic, ctx.tried_queries, ctx.anchor)
        if not queries:
            continue
        ctx.tried_queries.extend(queries)
        new_queries.extend(queries)
        question = svc.standalone_question(aspect, ctx.sq.main_topic)
        found = svc.retrieve(question, queries)
        kept = svc.relevance(question, found, ctx.anchor, ctx.context)
        for p in kept:
            key = svc.paper_key(p)
            if key in ctx.paper_keys or key in new_papers:
                continue
            p["matched_aspect"] = aspect
            new_papers[key] = p
    web = []
    if new_queries:
        web = [s for s in svc.web(new_queries) if s.url not in ctx.web_urls and len(s.snippet or "") >= 200]
    stats = {"queries": len(new_queries), "new_papers_found": len(new_papers), "new_web_found": len(web)}
    if not svc.can_store or not (new_papers or web):
        if not svc.can_store:
            stats["note"] = "dry run: not stored"
        return [], stats

    ranked = sorted(new_papers.values(), key=lambda p: p.get("relevance_score") or 0, reverse=True)[:_env_int("LOOP2_NEW_PAPERS", 3)]
    for p in ranked:
        p["sub_question_id"] = ctx.sq.id
    stored = svc.store_papers(ctx.query_id, svc.score(ranked)) if ranked else []
    for row in stored:
        ctx.paper_keys.add(svc.paper_key(row))
    usable = svc.parse([r["id"] for r in stored]) if stored else set()
    papers = svc.papers_by_ids(sorted(usable))
    ctx.papers.extend(papers)

    specs = _paper_specs(ctx, papers, open_idx)
    web_rows = []
    for s in web[:_env_int("LOOP2_NEW_WEB", 3)]:
        s.sub_question_id = ctx.sq.id
    chosen_web = web[:_env_int("LOOP2_NEW_WEB", 3)]
    if chosen_web:
        web_rows = svc.store_web(chosen_web)
        ctx.web_urls.update(w["url"] for w in web_rows)
    for w in web_rows:
        specs.append({"type": "web", "src": w, "selected": [(0, w.get("snippet") or "")], "weight": w.get("reliability_score"), "level": "web_snippet"})
    stats.update(new_papers_kept=len(ranked), new_papers_parsed=len(usable), new_web_kept=len(web_rows))
    return _digest_specs(ctx, specs, open_idx, svc, "queries"), stats


STEP_FUNCS: dict[str, Callable] = {"reselect": _step_reselect, "pool": _step_pool, "queries": _step_queries}


# ------------------------------------------------------------------------------------------------------------------ the loop
def run_subquestion(ctx: SubQuestionContext, cov: dict, candidates: list[dict], verdicts: dict, svc: Services, deadline: float):
    """Run the ladder for one sub-question. Returns (cov, candidates, verdicts, info); ctx.rows and ctx.chunk_lookup are extended in place.
    info is what gets stored in judge_stats['loop2']."""
    started = time.monotonic()
    counts = verdict_counts(candidates, verdicts)
    chosen, skipped = triage(cov, ctx.aspects, counts)
    aspects_info: dict[str, dict] = {}
    for text in cov.get("uncovered_aspects") or []:
        idx = ctx.aspects.index(text) if text in ctx.aspects else None
        c = counts.get(idx, Counter()) if idx is not None else Counter()
        aspects_info[text] = {"before": {k: c[k] for k in ("yes", "partial", "no")}, "status": "searched" if idx in chosen else skipped.get(idx, "skipped"),
                              "steps": [], "covered_by": None}
    for text in cov.get("unjudged_aspects") or []:
        aspects_info[text] = {"status": "unjudged_not_searched", "steps": [], "covered_by": None}

    step_log = []
    for step in steps():
        open_idx = [i for i in chosen if not _is_covered(cov, ctx.aspects[i])]
        if not open_idx:
            break
        if time.monotonic() > deadline:
            logger.warning("Loop 2: time budget used up; %d aspect(s) left as known gaps", len(open_idx))
            for i in open_idx:
                aspects_info[ctx.aspects[i]]["stopped"] = "time_budget"
            break
        t0 = time.monotonic()
        svc.progress(f"Loop 2 ({step}): {len(open_idx)} aspect(s) of '{ctx.sq.main_topic[:50]}'", step=step, aspects=len(open_idx))
        try:
            new_rows, stats = STEP_FUNCS[step](ctx, open_idx, svc)
        except Exception as e:                       # a failed step must never cost the run; the aspect stays a gap
            logger.exception("Loop 2: step %s failed for '%s'", step, ctx.sq.main_topic[:50])
            new_rows, stats = [], {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        for i in open_idx:
            aspects_info[ctx.aspects[i]]["steps"].append(step)
        before_findings = sum(len(r["findings"]) for r in ctx.rows)
        if new_rows:
            ctx.rows.extend(new_rows)
            candidates, verdicts = svc.judge(ctx)
            cov = coverage_check.check_coverage_judged(ctx.aspects, ctx.aspect_to_detail, ctx.details_for_coverage, ctx.rows, verdicts, candidates=candidates)
        newly = [ctx.aspects[i] for i in open_idx if _is_covered(cov, ctx.aspects[i])]
        for text in newly:
            aspects_info[text]["covered_by"] = step
        step_log.append({"step": step, "aspects": [ctx.aspects[i] for i in open_idx], "new_sources": len(new_rows),
                         "new_findings": sum(len(r["findings"]) for r in ctx.rows) - before_findings,
                         "new_verified": sum(r["verified_count"] for r in new_rows), "covered": newly,
                         "seconds": round(time.monotonic() - t0, 1), **stats})
        logger.info("Loop 2 [%s] %s: %d new source(s), %d of %d aspect(s) now covered (%.0f s)", ctx.sq.main_topic[:40], step,
                    len(new_rows), len(newly), len(open_idx), time.monotonic() - t0)

    for text, a in aspects_info.items():
        if a["status"] == "searched":
            a["status"] = "covered" if a["covered_by"] else "known_gap"
        elif a["status"] in ("skipped_triage", "skipped_cap", "skipped"):
            a["status"] = "known_gap_" + a["status"]
    info = {"triage": triage_mode(), "steps_enabled": steps(), "aspects": aspects_info, "steps": step_log,
            "seconds": round(time.monotonic() - started, 1), "searched": len(chosen), "covered": sum(1 for a in aspects_info.values() if a["status"] == "covered")}
    return cov, candidates, verdicts, info
