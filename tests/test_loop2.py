"""Loop 2 (A2, A3): triage, the ladder, stop rules, known gaps. Offline: fake services, fake embedder, real coverage rule."""
import hashlib
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import chunk_selector, coverage_check, loop2  # noqa: E402

ASPECTS = ["alpha topic", "beta topic", "gamma topic"]


class FakeEmbedder:
    def encode(self, texts, normalize_embeddings=True):
        out = []
        for t in texts:
            v = np.zeros(16, dtype=np.float32)
            for w in t.lower().split():
                v[sum(map(ord, w)) % 16] += 1.0
            out.append(v / (np.linalg.norm(v) + 1e-8))
        return np.array(out)


def h(claim):
    return hashlib.sha256(claim.encode()).hexdigest()[:16]


def paper(pid, n_chunks=12):
    words = ["alpha", "beta", "gamma", "delta", "topic", "model", "data", "result", "method", "study"]
    text = " ".join(" ".join(words[(i + j) % 10] + str(i % 4) for j in range(300)) for i in range(n_chunks))      # 300 words = one chunk each
    return {"id": pid, "title": pid, "abstract": "a", "combined_score": 0.8, "sections": [], "full_text": text, "has_full_text": True}


class FakeServices(loop2.Services):
    """Each step 'finds' what the script says; the judge says yes to every finding tagged for an aspect."""
    def __init__(self, covers=None, can_store=True):
        super().__init__()
        self.covers = covers or {}               # step -> list of aspect indexes that get 2 new yes findings from 2 sources
        self.can_store = can_store
        self.calls = []
        self.judged = 0
        self.digested = []
        self.fail_step = None

    # a digest returns findings for the aspects the prompt named (numbered 1..N in prompt order)
    def digest(self, sub_question, selected, aspects, main_topic, scope):
        self.digested.append((scope, list(aspects)))
        step = scope[1].split("#loop2-")[1]
        wanted = self.covers.get(step, [])
        tags = [{"detail": k + 1, "strength": "full"} for k, a in enumerate(aspects) if ASPECTS.index(a) in wanted] \
            if all(a in ASPECTS for a in aspects) else []
        if not tags:
            return [], 0
        return [{"claim": f"claim {scope[1]} {tags}", "quote": "q " * 5, "chunk_id": selected[0][0], "stance": "supports", "verified": True,
                 "answers_details": tags}], 0

    def judge(self, ctx):
        self.judged += 1
        candidates, verdicts = [], {}
        for row in ctx.rows:
            for f in row["findings"]:
                for tag in f.get("answers_details") or []:
                    idx = tag["detail"] - 1
                    c = {"aspect_idx": idx, "aspect_text": ctx.aspects[idx], "source_id": row["source_id"], "claim": f["claim"], "quote": f["quote"],
                         "similarity": 0.5, "item_id": f"{idx}{row['source_id']}"}
                    candidates.append(c)
                    verdicts[(idx, row["source_id"], h(f["claim"]))] = {"verdict": {"final": "yes"}}
        return candidates, verdicts

    def pool_rows(self, query_id, sq_id):
        self.calls.append("pool_rows")
        return [{"id": f"pool{i}", "title": f"P{i}", "combined_score": 0.5 - i / 100, "arxiv_id": "x"} for i in range(5)]

    def parse(self, ids):
        self.calls.append(("parse", list(ids)))
        return set(ids)

    def papers_by_ids(self, ids):
        return [paper(i) for i in ids]

    def gap_queries(self, aspect, sub_question, tried, anchor):
        self.calls.append(("gap_queries", aspect))
        return [f"query for {aspect}"]

    def standalone_question(self, aspect, sub_question):
        return f"What about {aspect}?"

    def retrieve(self, question, queries):
        self.calls.append(("retrieve", queries))
        return [{"title": f"New paper {k} {question}", "doi": f"10.1/{k}/{len(question)}", "relevance_score": 0.7 - k / 10} for k in range(2)]

    def relevance(self, question, papers, anchor, context):
        return papers

    def score(self, papers):
        return papers

    def store_papers(self, query_id, papers):
        return [{**p, "id": f"new{i}", "arxiv_id": None} for i, p in enumerate(papers)]

    def web(self, queries):
        return []

    def paper_key(self, p):
        return p.get("doi") or p.get("id") or p.get("title")

    def digest_workers(self):
        return 1

    def progress(self, message, **data):
        self.calls.append(("progress", message))


def make_ctx(rows=None, aspects=ASPECTS):
    sq = SimpleNamespace(id="sq1", main_topic="What is the topic?", queries=["q1"], detail_questions=["d"])
    return loop2.SubQuestionContext(query_id="q", sq=sq, aspects=list(aspects), aspect_to_detail=[0] * len(aspects), details_for_coverage=["d"],
                                    digest_aspects=list(aspects), rows=rows if rows is not None else [], chunk_lookup={},
                                    papers=[paper("p1"), paper("p2")], anchor="ml")


def base_cov(uncovered, reasons=None):
    return {"uncovered_aspects": list(uncovered), "unjudged_aspects": [], "uncovered_reasons": reasons or {a: "judged_insufficient" for a in uncovered},
            "judge_stats": {"candidates": 0}}


def base_verdicts(spec):
    """spec = {aspect idx: (yes, partial, no)} -> verdicts dict like the judge's."""
    out = {}
    for idx, (y, p, n) in spec.items():
        for kind, count in (("yes", y), ("partial", p), ("no", n)):
            for k in range(count):
                out[(idx, f"s{k}{kind}", h(f"{idx}{kind}{k}"))] = {"verdict": {"final": kind}}
    return out


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(chunk_selector, "get_embedder", lambda: FakeEmbedder())
    for k, v in {"CHUNK_EMBED_CACHE": "false", "LOOP2": "true", "LOOP2_TRIAGE": "r1", "LOOP2_STEPS": "reselect,pool,queries",
                 "LOOP2_MAX_ROUNDS": "3", "LOOP2_MIN_SIGNAL": "2", "LOOP2_MAX_ASPECTS": "4", "LOOP2_SYNTHESIS": "false",
                 "LOOP2_GAP_RULE": "strict", "LOOP2_QUERY_ROUNDS": "1"}.items():
        monkeypatch.setenv(k, v)


# ---------------------------------------------------------------------------------------------------------------- triage
def test_triage_searches_aspects_with_evidence_and_skips_invented_ones():
    cov = base_cov(ASPECTS)
    counts = loop2.verdict_counts([], base_verdicts({0: (1, 2, 0), 1: (0, 0, 3), 2: (0, 1, 1)}))
    chosen, skipped = loop2.triage(cov, ASPECTS, counts)
    assert chosen == [0]
    assert skipped[1] == "skipped_triage"
    assert 2 not in chosen and skipped[2] == "skipped_triage"          # 1 partial + 1 no: only one signal


def test_triage_always_searches_an_aspect_with_no_candidates():
    cov = base_cov(["alpha topic"], reasons={"alpha topic": "no_candidates"})
    chosen, _ = loop2.triage(cov, ASPECTS, {})
    assert chosen == [0]


def test_triage_all_mode_and_cap(monkeypatch):
    cov = base_cov(ASPECTS)
    counts = loop2.verdict_counts([], base_verdicts({0: (0, 0, 3), 1: (0, 0, 3), 2: (0, 0, 3)}))
    monkeypatch.setenv("LOOP2_TRIAGE", "all")
    monkeypatch.setenv("LOOP2_MAX_ASPECTS", "2")
    chosen, skipped = loop2.triage(cov, ASPECTS, counts)
    assert chosen == [0, 1] and skipped == {2: "skipped_cap"}


def test_unjudged_aspects_are_never_searched():
    cov = base_cov([])
    cov["unjudged_aspects"] = ["alpha topic"]
    chosen, _ = loop2.triage(cov, ASPECTS, {})
    assert chosen == []


# ---------------------------------------------------------------------------------------------------------------- the ladder
def run(svc, uncovered=("alpha topic", "beta topic"), spec=None, ctx=None, deadline=None):
    """Aspects not named in `uncovered` get two single-claim yes verdicts from two sources, so the coverage the loop recomputes matches."""
    ctx = ctx or make_ctx()
    spec = dict(spec or {0: (1, 2, 0), 1: (0, 3, 0), 2: (0, 0, 3)})
    for i, a in enumerate(ctx.aspects):
        if a not in uncovered:
            spec[i] = (2, 0, 0)
    verdicts = base_verdicts(spec)
    cov = coverage_check.check_coverage_judged(ctx.aspects, ctx.aspect_to_detail, ctx.details_for_coverage, ctx.rows, verdicts, candidates=None)
    return ctx, loop2.run_subquestion(ctx, cov, [], verdicts, svc, deadline or time.monotonic() + 60)


def test_ladder_stops_for_an_aspect_as_soon_as_it_is_covered():
    svc = FakeServices(covers={"reselect": [0], "pool": [1]})
    ctx, (cov, _, _, info) = run(svc)
    assert info["aspects"]["alpha topic"]["covered_by"] == "reselect"
    assert info["aspects"]["beta topic"]["covered_by"] == "pool"
    assert info["aspects"]["alpha topic"]["steps"] == ["reselect"]                 # not searched again in later steps
    assert info["aspects"]["beta topic"]["steps"] == ["reselect", "pool"]
    assert not any(c[0] == "gap_queries" for c in svc.calls if isinstance(c, tuple))     # step 3 never needed
    assert "alpha topic" not in cov["uncovered_aspects"] and "beta topic" not in cov["uncovered_aspects"]
    assert info["covered"] == 2 and [s["step"] for s in info["steps"]] == ["reselect", "pool"]


def test_remaining_aspects_become_known_gaps_after_the_last_step():
    svc = FakeServices(covers={})
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic", "gamma topic"))
    assert info["aspects"]["alpha topic"]["status"] == "known_gap"
    assert info["aspects"]["alpha topic"]["steps"] == ["reselect", "pool", "queries"]
    assert info["aspects"]["gamma topic"]["status"] == "known_gap_skipped_triage"      # 3 "no" only: no search spent
    assert svc.judged == 0                                                             # nothing new was found, so no judge call
    assert set(cov["uncovered_aspects"]) == {"alpha topic", "gamma topic"}


def test_new_sources_are_added_judged_and_the_coverage_is_recomputed():
    svc = FakeServices(covers={"queries": [0]})
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic",))
    assert info["aspects"]["alpha topic"]["covered_by"] == "queries"
    assert svc.judged == 1
    assert len(ctx.rows) >= 1 and all(f["loop2"]["step"] == "queries" for r in ctx.rows for f in r["findings"])
    assert any(k.startswith("new0:") for k in ctx.chunk_lookup) or any(k.startswith("pool") for k in ctx.chunk_lookup)
    assert ("retrieve", ["query for alpha topic"]) in svc.calls


def test_the_focus_digest_sees_only_the_aspects_being_searched_and_tags_map_back():
    svc = FakeServices(covers={"reselect": [1]})
    ctx, (cov, _, _, info) = run(svc, uncovered=("beta topic",), spec={1: (0, 3, 0)})
    scope, aspects = svc.digested[0]
    assert aspects == ["beta topic"]                                              # numbered 1 in the prompt
    tags = [t for r in ctx.rows for f in r["findings"] for t in f["answers_details"]]
    assert tags and all(t["detail"] == 2 for t in tags)                           # ... but index 2 for the judge (beta is aspect 2)


def test_without_focus_the_digest_sees_the_first_prompt_aspects(monkeypatch):
    monkeypatch.setenv("LOOP2_FOCUS_DIGEST", "false")
    svc = FakeServices(covers={})
    run(svc, uncovered=("beta topic",), spec={1: (0, 3, 0)})
    assert svc.digested[0][1] == ASPECTS


def test_a_failing_step_does_not_stop_the_ladder():
    class Boom(FakeServices):
        def pool_rows(self, *a):
            raise RuntimeError("database down")
    svc = Boom(covers={"queries": [0]})
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic",))
    assert info["aspects"]["alpha topic"]["covered_by"] == "queries"
    assert "error" in info["steps"][1] and "RuntimeError" in info["steps"][1]["error"]


def test_time_budget_stops_the_loop_and_marks_the_aspects():
    svc = FakeServices(covers={"reselect": [0]})
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic",), deadline=time.monotonic() - 1)
    assert info["steps"] == [] and info["aspects"]["alpha topic"]["stopped"] == "time_budget"
    assert info["aspects"]["alpha topic"]["status"] == "known_gap"
    assert ctx.rows == []


def test_steps_setting_limits_the_ladder(monkeypatch):
    monkeypatch.setenv("LOOP2_STEPS", "pool")
    svc = FakeServices(covers={"pool": [0]})
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic",))
    assert [s["step"] for s in info["steps"]] == ["pool"]
    monkeypatch.setenv("LOOP2_MAX_ROUNDS", "1")
    monkeypatch.setenv("LOOP2_STEPS", "reselect,pool,queries")
    assert loop2.steps() == ["reselect"]


def test_dry_run_counts_and_writes_nothing():
    svc = FakeServices(covers={"queries": [0]}, can_store=False)
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic",))
    assert info["aspects"]["alpha topic"]["status"] == "known_gap"
    assert ctx.rows == []
    assert [s.get("note") for s in info["steps"] if s["step"] == "queries"] == ["dry run: not stored"]
    assert any(c[0] == "parse" for c in svc.calls if isinstance(c, tuple))              # the pool step still parses (parse cache only)


def test_the_pool_is_not_read_twice():
    svc = FakeServices(covers={})
    ctx = make_ctx()
    run(svc, uncovered=("alpha topic",), ctx=ctx)
    first = set(ctx.pool_tried)
    assert first
    run(svc, uncovered=("alpha topic",), ctx=ctx)
    parsed = [c[1] for c in svc.calls if isinstance(c, tuple) and c[0] == "parse"]
    assert not (set(parsed[0]) & set(parsed[-1])) if len(parsed) > 1 else True


def test_select_more_chunks_skips_chunks_already_read():
    texts = chunk_selector.build_chunks(paper("p"))
    got = chunk_selector.select_more_chunks(texts, ["alpha topic"], {0, 1, 2}, per_query=3)
    assert len(got) == 3 and not ({i for i, _ in got} & {0, 1, 2})
    assert chunk_selector.select_more_chunks([], ["x"], set()) == []


def test_report_view_of_loop2_lists_known_gaps():
    from apps.api.services import report_service as rs
    assert rs._loop2_view({"judge_stats": {"candidates": 3}}) is None
    info = {"searched": 2, "covered": 1, "seconds": 12.5, "triage": "r1",
            "aspects": {"a": {"status": "covered", "covered_by": "pool", "steps": ["reselect", "pool"]},
                        "b": {"status": "known_gap", "covered_by": None, "steps": ["reselect", "pool", "queries"]},
                        "c": {"status": "known_gap_skipped_triage", "covered_by": None, "steps": []}},
            "steps": [{"step": "reselect", "aspects": ["a", "b"], "new_sources": 2, "new_verified": 3, "covered": [], "seconds": 4.0}]}
    view = rs._loop2_view({"judge_stats": {"loop2": info}})
    assert view["knownGaps"] == ["b", "c"] and view["covered"] == 1
    assert view["steps"][0] == {"step": "reselect", "aspects": 2, "newSources": 2, "newVerifiedFindings": 3, "covered": 0, "seconds": 4.0}
    assert [a["coveredBy"] for a in view["aspects"]] == ["pool", None, None]


def test_real_progress_reports_reach_the_event_sink():
    """The first live run failed here: a data key called 'step' collided with progress.report's own 'step' argument (the fake services hid it)."""
    from apps.api.graph.nodes import summarizer_node as sn
    from apps.api.services import progress
    events = []
    progress.register("run-x", events.append)
    try:
        svc = sn._Loop2Services("run-x")
        svc.progress("Loop 2 (reselect): 2 aspect(s)", loop2Step="reselect", aspects=2)
    finally:
        progress.unregister("run-x")
    assert events and events[0]["lane"] == "summarizer" and events[0]["step"] == "loop2" and events[0]["data"] == {"loop2Step": "reselect", "aspects": 2}


def test_a_real_loop2_failure_keeps_the_stage3_result(monkeypatch):
    """_run_loop2 never raises and puts the digests back as they were."""
    from apps.api.graph.nodes import summarizer_node as sn
    rows = [{"findings": []}]
    sq = SimpleNamespace(id="sq1", main_topic="t", queries=[])
    state = SimpleNamespace(task_plan=SimpleNamespace(domain_anchor="", domain_context=""))
    monkeypatch.setattr(sn.loop2, "run_subquestion", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sn._Loop2Services, "pool_rows", lambda self, q, s: [])
    monkeypatch.setattr(sn.db_service, "get_web_sources_for_stage3", lambda sid: [])
    cov = {"uncovered_aspects": ["a"]}
    out = sn._run_loop2("q", state, sq, 0, ["a"], [0], ["d"], ["a"], rows, {}, [], [], {}, cov, False, 0)
    assert out is cov and rows == [{"findings": []}]


def test_the_ladder_stops_when_every_digest_of_a_step_failed():
    """Q4, 2026-11-07: all 7 Groq keys were rate limited; the next steps would have failed the same way and cost time."""
    class Limited(FakeServices):
        def digest(self, *a, **k):
            return [], 1
    svc = Limited()
    ctx, (cov, _, _, info) = run(svc, uncovered=("alpha topic",))
    assert [s["step"] for s in info["steps"]] == ["reselect"]
    assert info["steps"][0]["digest_failed"] == info["steps"][0]["digest_total"] > 0
    assert info["aspects"]["alpha topic"]["stopped"] == "digests_failed" and info["aspects"]["alpha topic"]["status"] == "known_gap"
    assert ctx.rows == []


def test_a_digest_that_found_nothing_is_not_a_failure():
    class Empty(FakeServices):
        def digest(self, *a, **k):
            return [], 0
    ctx, (cov, _, _, info) = run(Empty(), uncovered=("alpha topic",))
    assert [s["step"] for s in info["steps"]] == ["reselect", "pool", "queries"]


# ---------------------------------------------------------------------------------------------------- synthesis and known gaps
def cands_for(spec):
    """Candidate dicts that match base_verdicts(spec), so the loop can read claims and sources."""
    out = []
    for idx, (y, p, n) in spec.items():
        for kind, count in (("yes", y), ("partial", p), ("no", n)):
            for k in range(count):
                out.append({"aspect_idx": idx, "aspect_text": ASPECTS[idx], "source_id": f"s{k}{kind}", "claim": f"{idx}{kind}{k}",
                            "quote": f"quote {idx}{kind}{k}", "similarity": 0.9 - k / 10, "item_id": f"{idx}{kind}{k}"})
    return out


class SynthServices(FakeServices):
    def __init__(self, accept=(), **kw):
        super().__init__(**kw)
        self.accept, self.items = set(accept), []

    def synthesize(self, items):
        self.items.extend(items)
        return [{"final": "yes" if it["aspect"] in self.accept else "partial", "reason": "r"} for it in items]


def run_synth(svc, spec, uncovered=("alpha topic",), gap_rule="strict", monkeypatch=None):
    ctx = make_ctx(rows=[{"source_id": f"row{i}", "evidence_level": "full_text", "verified_count": 1, "findings": [{"claim": "c", "verified": True}]}
                         for i in range(3)])             # three sources with a verified finding: "sufficient" also needs enough sources
    spec = dict(spec)
    for i, a in enumerate(ctx.aspects):
        if a not in uncovered:
            spec[i] = (2, 0, 0)
    verdicts, cands = base_verdicts(spec), cands_for(spec)
    cov = coverage_check.check_coverage_judged(ctx.aspects, ctx.aspect_to_detail, ctx.details_for_coverage, ctx.rows, verdicts, candidates=cands)
    return ctx, loop2.run_subquestion(ctx, cov, cands, verdicts, svc, time.monotonic() + 60)


def test_synthesis_covers_a_near_miss_before_any_search(monkeypatch):
    monkeypatch.setenv("LOOP2_SYNTHESIS", "true")
    svc = SynthServices(accept=["alpha topic"])
    ctx, (cov, _, _, info) = run_synth(svc, {0: (1, 3, 0)})
    a = info["aspects"]["alpha topic"]
    assert a["covered_by"] == "synthesis" and a["how"] == "synthesis" and a["status"] == "covered"
    assert info["covered_by_synthesis"] == 1 and info["steps"] == []                       # nothing was searched
    assert "alpha topic" not in cov["uncovered_aspects"] and cov["sufficient"] is True
    item = svc.items[0]
    assert item["aspect"] == "alpha topic" and item["claim"].count("(") >= 3 and "[1]" in item["quote"] and item["source_id"] == "synthesis"
    assert any(e.get("synthesis") for e in cov["aspect_evidence"][0])


def test_synthesis_needs_two_sources_and_a_judge_yes(monkeypatch):
    monkeypatch.setenv("LOOP2_SYNTHESIS", "true")
    svc = SynthServices(accept=[])                                                           # the judge says "partial" to every composite
    ctx, (cov, _, _, info) = run_synth(svc, {0: (0, 3, 0)})
    assert info["aspects"]["alpha topic"]["covered_by"] is None and "alpha topic" in cov["uncovered_aspects"]
    svc2 = SynthServices(accept=["alpha topic"])
    run_synth(svc2, {0: (0, 1, 2)})                                                           # one yes/partial source only: no composite is built
    assert svc2.items == []


def test_synthesis_is_off_when_switched_off(monkeypatch):
    monkeypatch.setenv("LOOP2_SYNTHESIS", "false")
    svc = SynthServices(accept=["alpha topic"])
    run_synth(svc, {0: (1, 3, 0)})
    assert svc.items == []


def test_core_rule_lets_an_aspect_without_evidence_stop_blocking(monkeypatch):
    monkeypatch.setenv("LOOP2_GAP_RULE", "core")
    svc = FakeServices(covers={})
    ctx, (cov, _, _, info) = run_synth(svc, {0: (0, 0, 3)}, uncovered=("alpha topic",))
    assert info["aspects"]["alpha topic"]["status"] == "known_gap_no_evidence"
    assert cov["sufficient"] is True and info["sufficient"] is True and info["sufficient_strict"] is False
    assert info["known_gaps_no_evidence"] == ["alpha topic"]
    assert "sufficient_strict" not in cov and "known_gap_aspects" not in cov               # not columns of coverage_results


def test_strict_rule_keeps_the_old_meaning(monkeypatch):
    monkeypatch.setenv("LOOP2_GAP_RULE", "strict")
    ctx, (cov, _, _, info) = run_synth(FakeServices(), {0: (0, 0, 3)})
    assert cov["sufficient"] is False and info["aspects"]["alpha topic"]["status"] == "known_gap_skipped_triage"


def test_a_near_miss_keeps_blocking_even_under_the_core_rule(monkeypatch):
    monkeypatch.setenv("LOOP2_GAP_RULE", "core")
    monkeypatch.setenv("LOOP2_SYNTHESIS", "true")
    svc = SynthServices(accept=[])
    ctx, (cov, _, _, info) = run_synth(svc, {0: (0, 4, 0)})
    a = info["aspects"]["alpha topic"]
    assert a["near_miss"] is True and a["status"] == "known_gap" and cov["sufficient"] is False


def test_an_aspect_whose_search_was_cut_short_keeps_blocking(monkeypatch):
    monkeypatch.setenv("LOOP2_GAP_RULE", "core")
    ctx = make_ctx()
    spec = {0: (0, 2, 1), 1: (2, 0, 0), 2: (2, 0, 0)}
    verdicts, cands = base_verdicts(spec), cands_for(spec)
    cov = coverage_check.check_coverage_judged(ctx.aspects, ctx.aspect_to_detail, ctx.details_for_coverage, ctx.rows, verdicts, candidates=cands)
    _, _, _, info = loop2.run_subquestion(ctx, cov, cands, verdicts, FakeServices(), time.monotonic() - 1)      # deadline already past
    assert info["aspects"]["alpha topic"]["stopped"] == "time_budget" and info["aspects"]["alpha topic"]["status"] == "known_gap"


def test_query_rounds_repeat_the_queries_step(monkeypatch):
    monkeypatch.setenv("LOOP2_QUERY_ROUNDS", "2")
    monkeypatch.setenv("LOOP2_MAX_ROUNDS", "3")
    assert loop2.steps() == ["reselect", "pool", "queries", "queries"]
    monkeypatch.setenv("LOOP2_QUERY_ROUNDS", "1")
    assert loop2.steps() == ["reselect", "pool", "queries"]


def test_the_judge_gets_a_larger_candidate_cap_in_loop2(monkeypatch):
    seen = {}
    monkeypatch.setattr(loop2.evidence_judge, "run_judge_for_subquestion", lambda *a, **k: seen.update(k) or ([], {}))
    monkeypatch.setenv("LOOP2_CANDIDATES_PER_ASPECT", "12")
    loop2.Services().judge(make_ctx())
    assert seen["candidates_per_aspect"] == 12


def test_report_marks_synthesis_and_known_gaps():
    from apps.api.services import report_service as rs
    rows = rs._aspect_rows(["a", "b", "c"], {"aspect_evidence": {"0": [{"verdict": "yes", "source_id": "s1", "synthesis": True}, {"verdict": "yes", "source_id": "s2", "synthesis": True}],
                                                                  "1": [{"verdict": "yes", "source_id": "s1"}, {"verdict": "yes", "source_id": "s2"}]},
                                             "uncovered_aspects": ["c"], "uncovered_reasons": {"c": "judged_insufficient"}})
    assert [r["coveredBy"] for r in rows] == ["synthesis", "single_claims", None]
    view = rs._loop2_view({"judge_stats": {"loop2": {"searched": 1, "covered": 1, "covered_by_synthesis": 1, "gap_rule": "core", "sufficient_strict": False,
                                                      "known_gaps_no_evidence": ["c"], "aspects": {"a": {"status": "covered", "how": "synthesis", "steps": []}}, "steps": []}}})
    assert view["coveredBySynthesis"] == 1 and view["sufficientStrict"] is False and view["knownGapsNoEvidence"] == ["c"]
    assert view["aspects"][0]["how"] == "synthesis"


def test_core_rule_does_not_trust_an_empty_result_when_the_first_digests_failed(monkeypatch):
    """Q3, 2026-11-07 17:22: the Groq quota was gone, every digest failed, and 'no evidence' looked like a finding."""
    monkeypatch.setenv("LOOP2_GAP_RULE", "core")
    ctx = make_ctx(rows=[{"source_id": f"row{i}", "evidence_level": "full_text", "verified_count": 1, "findings": [{"claim": "c", "verified": True}]} for i in range(3)])
    ctx.digest_failures = 4
    spec = {0: (0, 0, 3), 1: (2, 0, 0), 2: (2, 0, 0)}
    verdicts, cands = base_verdicts(spec), cands_for(spec)
    cov = coverage_check.check_coverage_judged(ctx.aspects, ctx.aspect_to_detail, ctx.details_for_coverage, ctx.rows, verdicts, candidates=cands)
    out, _, _, info = loop2.run_subquestion(ctx, cov, cands, verdicts, FakeServices(), time.monotonic() + 60)
    assert info["aspects"]["alpha topic"]["status"] == "known_gap_skipped_triage" and out["sufficient"] is False
