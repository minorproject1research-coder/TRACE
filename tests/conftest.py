"""Shared test setup: no test may read, write or delete the real caches under reports/ or .cache/.

The real aspect cache holds the aspect splits that stored Stage 3 runs were judged against, and the judge cache holds judge verdicts.
Tests that wiped or filled them (with mock splits such as "advantages of X") made later audits re-split aspects with the LLM and get
different aspects than the stored run. Every test now gets its own empty caches in a temp directory.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolated_caches(tmp_path, monkeypatch):
    from apps.api.agents.stage3_summarizer import detail_aspects, evidence_judge
    from apps.api.services import trace_llm_service      # noqa: F401  (imports load .env once, BEFORE the variables are cleared below)
    for name in ("JUDGE_URL", "JUDGE_API_KEY", "TRACE_LLM_URL", "TRACE_LLM_API_KEY", "x-api-key", "X_API_KEY", "JUDGE_MODEL_ID", "JUDGE_CACHE_PATH"):
        monkeypatch.delenv(name, raising=False)           # tests must never reach the real model server by accident
    monkeypatch.setattr(detail_aspects, "ASPECT_CACHE_PATH", tmp_path / "aspect_cache.json")
    monkeypatch.setattr(evidence_judge, "JUDGE_CACHE_PATH", tmp_path / "judge_cache.json")
    monkeypatch.setenv("DIGEST_CACHE_DIR", str(tmp_path / "digest_cache"))
    monkeypatch.setenv("DOMAIN_ANCHOR_CACHE_DIR", str(tmp_path / "domain_anchor_cache"))
    monkeypatch.delenv("DOMAIN_ANCHOR", raising=False)        # tests choose the switch themselves
    monkeypatch.setenv("PLAN_CACHE_DIR", str(tmp_path / "plan_cache"))
    for name in ("PLAN_CACHE", "PLAN_CACHE_TAG", "LOOP2", "TOPIC_ASPECT", "STAGE4_CACHE"):
        monkeypatch.delenv(name, raising=False)               # off unless the test switches it on (the real .env may have Loop 2 and Stage 4 on)
    monkeypatch.setenv("FACTCHECK", "false")                  # explicit "false": a module imported later calls load_dotenv() and would bring the .env value back
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "1")             # tests that look at the order of writes and events need the sub-questions one by one
    monkeypatch.setenv("STAGE4_SQ_WORKERS", "1")             # the real .env enables 2; tests that count simultaneous Stage 4 jobs choose it themselves
    monkeypatch.setenv("STAGE5_STYLE", "attributed")           # the existing Stage 5 tests are written for the s5-v2 wording; the natural style has its own tests
    monkeypatch.setenv("STAGE5_EMBED_SELECT", "false")         # tests must not load the embedding model; the embedding path has its own test with a fake
    monkeypatch.setenv("PLAN_ANSWER_SUBQUESTIONS", "0")        # the real step calls Groq; its own tests switch it on with a fake chat
    monkeypatch.setenv("STAGE3_WARM_CHUNKS", "false")        # the warm-ups read the database, the embedder and Groq: only their own tests switch them on
    monkeypatch.setenv("STAGE3_WARM_ASPECTS", "false")
    monkeypatch.setenv("GROQ_USAGE_LOG", "off")               # tests never write the real usage log
    monkeypatch.setenv("STAGE5_CACHE_DIR", str(tmp_path / "stage5_cache"))     # Stage 5 writes its validated replies here, never into the real .cache/stage5
    monkeypatch.setenv("STAGE5", "false")                     # explicit "false" like FACTCHECK: the real .env may switch the written report on
    yield
