"""Offline tests of the digest cache (fake LLM, no Groq calls)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import digest_cache, digest_generator as dg  # noqa: E402

CHUNKS = [(0, "Speculative decoding drafts several tokens and verifies them in one pass of the large model.")]
REPLY = {"findings": [{"claim": "It drafts tokens.", "quote": "Speculative decoding drafts several tokens", "chunk_id": 0,
                       "stance": "neutral", "answers_details": [{"detail": 1, "strength": "full"}]}]}


@pytest.fixture
def fake_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("DIGEST_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("DIGEST_CACHE", "true")
    calls = []

    def fake(prompt, *, temperature=0.1, seed=None, purpose="other"):
        calls.append((temperature, seed))
        if isinstance(fake.reply, Exception):
            raise fake.reply
        return fake.reply
    fake.reply = REPLY
    monkeypatch.setattr(dg, "squeezer_json", fake)
    return fake, calls


def run(chunks=CHUNKS, scope=("sq1", "src1"), aspects=("how does it work",)):
    return dg.generate_digest("q", chunks, detail_aspects=list(aspects), main_topic="speculative decoding", cache_scope=scope)


def test_second_call_is_served_from_cache_and_identical(fake_llm):
    fake, calls = fake_llm
    a, b = run(), run()
    assert len(calls) == 1 and a == b and a[0]["verified"] is True


def test_cache_returns_the_old_reply_even_if_the_model_would_now_answer_differently(fake_llm):
    fake, calls = fake_llm
    first = run()
    fake.reply = {"findings": []}
    assert run() == first and len(calls) == 1


def test_no_scope_means_no_cache(fake_llm):
    fake, calls = fake_llm
    run(scope=None); run(scope=None)
    assert len(calls) == 2


def test_other_source_other_aspects_or_other_chunks_miss(fake_llm):
    fake, calls = fake_llm
    run()
    run(scope=("sq1", "src2"))
    run(scope=("sq2", "src1"))
    run(aspects=("how does it work", "advantages"))
    run(chunks=[(0, CHUNKS[0][1] + " Extra sentence.")])
    assert len(calls) == 5


def test_failed_call_is_not_cached(fake_llm):
    fake, calls = fake_llm
    fake.reply = RuntimeError("429")
    assert run() == []
    fake.reply = REPLY
    assert len(run()) == 1 and len(calls) == 2


def test_empty_findings_reply_is_cached(fake_llm):
    fake, calls = fake_llm
    fake.reply = {"findings": []}
    assert run() == [] and run() == [] and len(calls) == 1


def test_switch_off(fake_llm, monkeypatch):
    fake, calls = fake_llm
    monkeypatch.setenv("DIGEST_CACHE", "false")
    run(); run()
    assert len(calls) == 2


def test_sampling_settings_are_part_of_the_key(fake_llm, monkeypatch):
    fake, calls = fake_llm
    run()
    monkeypatch.setattr(dg, "DIGEST_TEMPERATURE", 0.0)
    monkeypatch.setattr(dg, "DIGEST_SEED", 7)
    run()
    assert calls == [(0.1, None), (0.0, 7)]


def test_corrupt_cache_file_is_regenerated(fake_llm, tmp_path):
    fake, calls = fake_llm
    run()
    for f in (tmp_path / "cache").glob("*.json"):
        f.write_text("{not json", encoding="utf-8")
    assert len(run()) == 1 and len(calls) == 2


# ---------------------------------------------------------------- the scope comes from content, so a new run of the same question hits the cache
def test_the_scope_is_the_same_for_the_same_paper_and_question_under_new_database_ids():
    paper_run1 = {"id": "uuid-run-1", "title": "A Survey of GANs", "arxiv_id": "2001.00001v2"}
    paper_run2 = {"id": "uuid-run-2", "title": "A Survey of GANs", "arxiv_id": "2001.00001v3"}                 # same paper, new row id, newer arXiv version
    a = digest_cache.content_scope("What are  GANs?", "paper", paper_run1, ids=("sq-1", "uuid-run-1"))
    b = digest_cache.content_scope("what are gans?", "paper", paper_run2, ids=("sq-2", "uuid-run-2"))
    assert a == b == ("what are gans?", "arxiv:2001.00001")
    assert digest_cache.content_scope("q", "paper", paper_run1, suffix="#loop2-reselect")[1].endswith("#loop2-reselect")


def test_a_different_paper_or_question_gets_another_scope_and_web_pages_are_told_by_url():
    p1, p2 = {"id": "1", "title": "Paper One"}, {"id": "2", "title": "Paper Two"}
    assert digest_cache.content_scope("q", "paper", p1) != digest_cache.content_scope("q", "paper", p2)
    assert digest_cache.content_scope("q1", "paper", p1) != digest_cache.content_scope("q2", "paper", p1)
    w1, w2 = {"id": "w-a", "url": "https://x.org/a", "title": "T"}, {"id": "w-b", "url": "https://x.org/a", "title": "T"}
    assert digest_cache.content_scope("q", "web", w1) == digest_cache.content_scope("q", "web", w2) == ("q", "web:https://x.org/a")


def test_the_old_id_scope_can_be_switched_back_on(monkeypatch):
    monkeypatch.setenv("DIGEST_CACHE_SCOPE", "id")
    assert digest_cache.content_scope("q", "paper", {"id": "u", "title": "T"}, suffix="#x", ids=("sq-1", "u")) == ("sq-1", "u#x")


def test_a_second_run_with_new_ids_reuses_the_stored_digest(monkeypatch, tmp_path):
    monkeypatch.setenv("DIGEST_CACHE_DIR", str(tmp_path / "dc"))
    calls = []
    monkeypatch.setattr(dg, "squeezer_json", lambda prompt, **kw: calls.append(prompt) or {"findings": []})
    chunks = [(0, "Some chunk text about GANs.")]
    paper1, paper2 = {"id": "u1", "title": "T", "arxiv_id": "2001.00001"}, {"id": "u2", "title": "T", "arxiv_id": "2001.00001"}
    s1 = digest_cache.content_scope("What are GANs?", "paper", paper1, ids=("sq-1", "u1"))
    s2 = digest_cache.content_scope("What are GANs?", "paper", paper2, ids=("sq-2", "u2"))
    dg.generate_digest("What are GANs?", chunks, detail_aspects=["a"], main_topic="GANs", cache_scope=s1)
    dg.generate_digest("What are GANs?", chunks, detail_aspects=["a"], main_topic="GANs", cache_scope=s2)
    assert len(calls) == 1                                                  # the second run asked no model
