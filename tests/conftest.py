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
    for name in ("PLAN_CACHE", "PLAN_CACHE_TAG"):
        monkeypatch.delenv(name, raising=False)               # off unless the test switches it on
    yield
