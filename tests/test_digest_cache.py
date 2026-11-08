"""Offline tests of the digest cache (fake LLM, no Groq calls)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import digest_generator as dg  # noqa: E402

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
