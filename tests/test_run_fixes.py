"""Tests for the fixes found while reading the 2026-11-05 16:08 run: digest failures must surface, the embedder must not need the network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import digest_generator as dg  # noqa: E402


def test_failed_digest_call_returns_empty_by_default_and_raises_when_strict(monkeypatch):
    monkeypatch.setenv("DIGEST_CACHE", "false")
    monkeypatch.setattr(dg, "squeezer_json", lambda *a, **k: (_ for _ in ()).throw(ValueError("Expecting property name")))
    chunks = [(0, "some chunk text " * 10)]
    assert dg.generate_digest("q", chunks, detail_aspects=["a"], main_topic="t", cache_scope=("s", "x")) == []
    with pytest.raises(ValueError):
        dg.generate_digest("q", chunks, detail_aspects=["a"], main_topic="t", cache_scope=("s", "x"), strict=True)


def test_embedder_loads_the_local_copy_first(monkeypatch):
    from apps.api.agents.stage2_retrieval import relevance_filter as rf
    calls = []

    class Fake:
        def __init__(self, name, **kw):
            calls.append(kw)
    monkeypatch.setattr(rf, "SentenceTransformer", Fake)
    monkeypatch.setattr(rf, "_embedder", None)
    rf.get_embedder()
    assert calls == [{"local_files_only": True}]


def test_embedder_downloads_when_the_local_copy_is_missing(monkeypatch):
    from apps.api.agents.stage2_retrieval import relevance_filter as rf
    calls = []

    class Fake:
        def __init__(self, name, **kw):
            calls.append(kw)
            if kw.get("local_files_only"):
                raise OSError("not in the local cache")
    monkeypatch.setattr(rf, "SentenceTransformer", Fake)
    monkeypatch.setattr(rf, "_embedder", None)
    rf.get_embedder()
    assert calls == [{"local_files_only": True}, {}]


def test_missing_openalex_key_is_announced(caplog):
    from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
    with caplog.at_level("WARNING"):
        agent = PaperRetrievalAgent(openalex_api_key="")
    assert agent._openalex_pool is None
    assert "OpenAlex is NOT searched" in " ".join(r.getMessage() for r in caplog.records)


def test_present_openalex_key_gives_no_warning(caplog):
    from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
    with caplog.at_level("WARNING"):
        agent = PaperRetrievalAgent(openalex_api_key="k1,k2")
    assert agent._openalex_pool is not None
    assert "OpenAlex is NOT searched" not in " ".join(r.getMessage() for r in caplog.records)
