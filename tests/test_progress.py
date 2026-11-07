"""Step-level progress of a run (services/progress.py and its reports in the three nodes). Offline: stubs, no database, no LLM."""
import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage2_retrieval import relevance_filter  # noqa: E402
from apps.api.graph.nodes import paper_retrieval_node as prn, summarizer_node as sn, web_search_node as wsn  # noqa: E402
from apps.api.services import progress, run_manager as rm  # noqa: E402

QID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def seen():
    """Collects every report for QID."""
    got: list[dict] = []
    progress.register(QID, got.append)
    yield got
    progress.unregister(QID)


def steps(got, lane=None):
    return [(r["lane"], r["step"], r["state"]) for r in got if lane is None or r["lane"] == lane]


# ------------------------------------------------------------------------------------------------------------------ the module
def test_reports_reach_the_registered_sink_and_stop_after_unregister():
    got = []
    progress.register(QID, got.append)
    progress.report(QID, "papers", "parsing", "running", "Parsed 1 of 5", usable=1, target=5)
    progress.unregister(QID)
    progress.report(QID, "papers", "parsing", "completed")
    assert got == [{"lane": "papers", "step": "parsing", "state": "running", "message": "Parsed 1 of 5", "data": {"usable": 1, "target": 5}}]


def test_a_report_never_breaks_the_caller():
    def boom(_):
        raise RuntimeError("sink is broken")
    progress.register(QID, boom)
    try:
        progress.report(QID, "web", "search")           # must not raise
        progress.report(None, "web", "search")          # no run id: nothing to do
        progress.report("not-registered", "web", "search")
    finally:
        progress.unregister(QID)


# --------------------------------------------------------------------------------------------------- run manager -> events
class NodeLikeGraph:
    """A graph whose 'nodes' report progress like the real ones, from different threads (the two branches run at the same time)."""
    def stream(self, state, stream_mode):
        import threading
        qid = state.query_id
        sq = SimpleNamespace(main_topic="What are SSMs?", queries=["a", "b"])
        yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[sq], domain_anchor=None)}}

        def papers():
            progress.report(qid, "papers", "branch", "running", "Paper retrieval started")
            progress.report(qid, "papers", "parsing", "running", "Parsed 2 of 5", usable=2, target=5)
        def web():
            progress.report(qid, "web", "branch", "running", "Web search started")
            progress.report(qid, "web", "search", "completed", "Found 9 web sources", found=9)
        threads = [threading.Thread(target=papers), threading.Thread(target=web)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        yield {"paper_retrieval": {"paper_results": [{}]}}
        yield {"web_search": {"web_sources": [{}]}}
        progress.report(qid, "summarizer", "digest", "running", "Read 3 of 8 sources", done=3, total=8)
        yield {"summarizer": {"digests": [1], "coverage": {"a": {"sufficient": True}}}}


def test_reports_become_events_in_order_with_the_right_stage():
    manager = rm.RunManager(graph_factory=lambda: NodeLikeGraph(), max_workers=1, max_pending=1)
    try:
        rec = manager.submit("How do state space models compare with transformers?")
        deadline = time.time() + 5
        while not rec.finished and time.time() < deadline:
            time.sleep(0.05)
        assert rec.status == "completed"
        ev = rec.events_from(0)
        assert [e["seq"] for e in ev] == list(range(len(ev)))
        started = [e for e in ev if e["event"] == "branch_started"]
        assert {e["data"]["branch"] for e in started} == {"papers", "web"} and all(e["stage"] == "retrieval" for e in started)
        step_ev = [e for e in ev if e["event"] == "step"]
        assert {(e["data"]["lane"], e["data"]["step"]) for e in step_ev} == {("papers", "parsing"), ("web", "search"), ("summarizer", "digest")}
        assert next(e for e in step_ev if e["data"]["lane"] == "summarizer")["stage"] == "summarizer"
        parsing = next(e for e in step_ev if e["data"]["step"] == "parsing")
        assert parsing["data"] == {"lane": "papers", "step": "parsing", "state": "running", "usable": 2, "target": 5} and parsing["message"] == "Parsed 2 of 5"
        # the step events sit between the stage's start and end, and the old events are unchanged
        names = [e["event"] for e in ev]
        assert names[0] == "run_queued" and names[-1] == "run_completed" and names.count("branch_completed") == 2
        assert names.index("stage_started") < names.index("branch_started") < names.index("branch_completed")
        progress.report(rec.id, "papers", "parsing", "completed")                 # the sink is gone once the run ends
        assert len(rec.events_from(0)) == len(ev)
    finally:
        manager.shutdown()


# ------------------------------------------------------------------------------------------------------------ relevance filter
def test_filter_relevant_reports_what_the_judge_did(monkeypatch):
    papers = [{"title": f"P{i}"} for i in range(5)]
    monkeypatch.setattr(relevance_filter, "embedding_prefilter", lambda q, ps, top_k, min_similarity: ps[:3])
    monkeypatch.setattr(relevance_filter, "USE_LLM_JUDGMENT", True)
    verdicts = {"P0": {"relevant": True, "confidence": 0.9}, "P1": {"relevant": False, "confidence": 0.9}, "P2": None}
    monkeypatch.setattr(relevance_filter, "llm_judge_relevance", lambda q, p: verdicts[p["title"]])
    monkeypatch.setattr(relevance_filter, "JUDGE_WORKERS", 1)
    stats: dict = {}
    passed = relevance_filter.filter_relevant("What is X?", papers, stats=stats)
    assert [p["title"] for p in passed] == ["P0", "P2"]              # P2 had no judgment: kept on the embedding decision
    assert stats["candidates"] == 5 and stats["shortlisted"] == 3 and stats["judged"] == 2 and stats["passed"] == 2 and stats["judgeUnavailable"] == 1
    assert relevance_filter.filter_relevant("What is X?", papers) is not None            # stats stays optional


# ---------------------------------------------------------------------------------------------------------------- web node
def test_web_node_reports_search_scoring_and_store(monkeypatch, seen):
    async def search_all(queries):
        return [SimpleNamespace(sub_question_id=None) for _ in queries]
    monkeypatch.setattr(wsn.web_search_agent, "search_all", search_all)
    monkeypatch.setattr(wsn.reliability_scorer, "score_all", lambda xs: xs)
    stored = []
    monkeypatch.setattr(wsn.db_service, "write_web_sources", stored.extend)
    state = SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=[SimpleNamespace(id="s1", queries=["a", "b"]), SimpleNamespace(id="s2", queries=["c"])]))
    out = wsn.web_search_node(state)
    assert len(out["web_sources"]) == 3 and len(stored) == 3
    s = steps(seen, "web")
    assert s[0] == ("web", "branch", "running")
    for want in [("web", "search", "running"), ("web", "search", "completed"), ("web", "scoring", "completed"), ("web", "store", "completed")]:
        assert want in s
    done = [r["data"] for r in seen if r["step"] == "search" and r["state"] == "running" and "done" in r["data"]]
    assert [d["done"] for d in done if d["done"] > 0] == [1, 2] and done[-1]["found"] == 3


# -------------------------------------------------------------------------------------------------------------- papers node
class FakeAgent:
    def __init__(self, max_results_per_query=10):
        pass

    async def retrieve(self, sub_question, query_variants, enrich):
        return [{"title": f"{sub_question} #{i}"} for i in range(4)]

    async def enrich_papers(self, papers):
        return papers[:-1]                              # one paper is dropped when citations are fetched

    async def parse_papers(self, paper_ids):
        # the first paper of every round has usable text, the others do not
        return [SimpleNamespace(retrieved_paper_id=pid, full_text="x" * (4000 if i == 0 else 10)) for i, pid in enumerate(paper_ids)]


class FakeTable:
    def __init__(self, rows):
        self.rows = rows
    def select(self, *_): return self
    def eq(self, *_): return self
    def execute(self): return SimpleNamespace(data=self.rows)


def test_papers_node_reports_every_step_including_parsing_rounds(monkeypatch, seen):
    monkeypatch.setattr(prn, "PaperRetrievalAgent", FakeAgent)
    def fake_filter(sub_question, papers, anchor="", context="", stats=None):
        stats.update(candidates=len(papers), shortlisted=3, judged=3, passed=2, judgeUnavailable=0, backend="server")
        return papers[:2]
    monkeypatch.setattr(prn.relevance_filter, "filter_relevant", fake_filter)
    monkeypatch.setattr(prn.relevance_filter, "compute_combined_score", lambda p: {**p, "combined_score": 0.5})
    monkeypatch.setattr(prn.reliability_scorer, "score_all", lambda ps: ps)
    stored = []
    monkeypatch.setattr(prn.db_service, "write_retrieved_papers", lambda qid, ps: stored.extend(ps))
    rows = [{"id": f"p{i}", "sub_question_id": "s1" if i < 3 else "s2", "title": f"T{i}", "combined_score": 0.9 - i / 10, "arxiv_id": None, "pdf_url": None, "doi": f"10.1/{i}"} for i in range(6)]
    monkeypatch.setattr(prn.db_service, "supabase", SimpleNamespace(table=lambda name: FakeTable(rows)))
    monkeypatch.setattr(prn.db_service, "get_pdf_failures", lambda keys, *a: {})
    monkeypatch.setattr(prn, "PARSE_TOP_N", 2)
    sqs = [SimpleNamespace(id="s1", main_topic="Q1", queries=["a"], papers=[]), SimpleNamespace(id="s2", main_topic="Q2", queries=["b", "c"], papers=[])]
    state = SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=sqs, domain_anchor="", domain_context=""))
    out = prn.paper_retrieval_node(state)
    assert len(out["paper_results"]) == 3 and len(stored) == 3             # 2 sub-questions x 2 passed = 4, one dropped by the citation step

    s = steps(seen, "papers")
    order = [x[1] for x in s]
    assert order[0] == "branch"
    first_of = lambda step: order.index(step)
    assert first_of("search") < first_of("relevance_filter") < first_of("citations") < first_of("scoring") < first_of("store") < first_of("parsing")
    for want in [("papers", "search", "completed"), ("papers", "relevance_filter", "completed"), ("papers", "citations", "completed"),
                 ("papers", "scoring", "completed"), ("papers", "store", "completed"), ("papers", "parsing", "completed")]:
        assert want in s
    rel = next(r for r in seen if r["step"] == "relevance_filter" and r["state"] == "completed")["data"]
    assert rel["candidates"] == 8 and rel["judged"] == 6 and rel["passed"] == 4 and rel["backend"] == "server"
    assert next(r for r in seen if r["step"] == "search" and r["state"] == "completed")["data"]["candidates"] == 8
    parse = [r["data"] for r in seen if r["step"] == "parsing"]
    assert parse[0]["target"] == 4 and parse[0]["usable"] == 0               # 2 per sub-question, announced before the first round
    usable = [d["usable"] for d in parse]
    assert usable == sorted(usable) and usable[-1] == 2                      # only the first paper of each round has text; counts never go backwards
    assert next(r for r in seen if r["step"] == "parsing" and r["state"] == "completed")["data"]["attempted"] >= 4


# --------------------------------------------------------------------------------------------------------- summarizer node
def test_summarizer_reports_digest_progress_from_worker_threads(monkeypatch, seen):
    sub_questions = [SimpleNamespace(id=f"s{i}", main_topic=f"Topic {i}?", detail_questions=["d"]) for i in range(2)]
    monkeypatch.setattr(sn.detail_aspects, "flatten_aspects", lambda details, sq_id, topic: (["a1"], {"a1": "d"}))
    monkeypatch.setattr(sn.detail_aspects, "with_topic_aspect", lambda a, m, d, t, enabled=None: (a + ["t"], m, d))
    monkeypatch.setattr(sn.detail_aspects, "merge_mode", lambda: "x")
    monkeypatch.setattr(sn.db_service, "get_papers_for_stage3", lambda qid, sq_id: [{"id": f"{sq_id}-p{i}", "title": "P", "combined_score": 0.8, "has_full_text": True} for i in range(3)])
    monkeypatch.setattr(sn.db_service, "get_web_sources_for_stage3", lambda sq_id: [{"id": f"{sq_id}-w", "title": "W", "snippet": "x" * 300, "reliability_score": 0.4}])
    monkeypatch.setattr(sn.chunk_selector, "build_chunks", lambda p: [])
    monkeypatch.setattr(sn.chunk_selector, "select_chunks", lambda *a, **k: [(0, "text")])
    monkeypatch.setattr(sn.digest_generator, "generate_digest", lambda *a, **k: [{"claim": "c", "quote": "q", "verified": True, "stance": "supports"}])
    monkeypatch.setattr(sn.evidence_judge, "run_judge_for_subquestion", lambda aspects, rows, lookup, **kw: ([], {}))
    monkeypatch.setattr(sn.coverage_check, "check_coverage_judged", lambda *a, **k: {"sufficient": True, "judge_used": True, "judge_stats": {}, "uncovered_aspects": []})
    written = {}
    monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: written.setdefault("digests", rows))
    monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: written.setdefault("coverage", rows))
    monkeypatch.setattr(sn, "MAX_PAPERS", 3)
    monkeypatch.setattr(sn, "_workers", lambda: 4)
    state = SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=sub_questions))
    out = sn.summarizer_node(state)
    assert len(out["digests"]) == 8 and len(written["digests"]) == 8

    prep = next(r for r in seen if r["step"] == "prepare" and r["state"] == "completed")["data"]
    assert prep == {"jobs": 8, "papers": 6, "web": 2}
    digest = [r["data"] for r in seen if r["step"] == "digest" and r["state"] == "running" and r["data"]["total"] == 8]
    assert [d["done"] for d in digest] == list(range(0, 9))                      # 0..8, each count seen once even with 4 threads
    judge = [r["data"] for r in seen if r["step"] == "judge"]
    assert judge[0]["done"] == 0 and judge[-1]["sufficientSubQuestions"] == 2 and judge[-1]["done"] == 2
    order = [(r["step"], r["state"]) for r in seen]
    assert order.index(("digest", "completed")) < order.index(("judge", "completed")) < order.index(("store", "completed"))
