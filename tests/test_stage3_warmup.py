"""STAGE3_WARM_CHUNKS and STAGE3_WARM_ASPECTS: Stage 3 work done earlier, into the caches Stage 3 reads. Offline: fakes only, no network, no models."""
import asyncio
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
from apps.api.agents.stage3_summarizer import chunk_selector, detail_aspects, warmup


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CHUNK_EMBED_CACHE", "true")
    monkeypatch.setenv("CHUNK_EMBED_CACHE_DIR", str(tmp_path / "chunks"))
    monkeypatch.delenv("STAGE3_WARM_CHUNKS", raising=False)
    monkeypatch.delenv("STAGE3_WARM_ASPECTS", raising=False)
    monkeypatch.delenv("STAGE3_WARM_WAIT_SECONDS", raising=False)


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def encode(self, texts, normalize_embeddings=True, **kw):
        self.calls.append(len(texts))
        return np.ones((len(texts), 4), dtype="float32")


def paper(n_chunks, full_text=True, pid="p1"):
    words = " ".join(f"w{i}" for i in range(300))                      # the chunker cuts 300 words per chunk, so n_chunks x 300 words give n_chunks chunks
    text = " ".join([words] * n_chunks)
    return {"id": pid, "title": "T", "abstract": "A " * 40, "sections": [], "full_text": text if full_text else "", "has_full_text": full_text}


def patch_db(monkeypatch, papers):
    monkeypatch.setattr(warmup.db_service, "get_papers_by_ids", lambda ids: [papers[i] for i in ids if i in papers])


# ---------------------------------------------------------------------------------------------------------------- chunk embeddings
def test_a_long_parsed_paper_is_embedded_into_the_cache_and_stage_3_then_finds_it(monkeypatch):
    emb = FakeEmbedder()
    monkeypatch.setattr(chunk_selector, "get_embedder", lambda: emb)
    p = paper(12)
    patch_db(monkeypatch, {"p1": p})
    assert warmup.warm_paper("p1") == 12 and emb.calls == [12]
    chunk_selector.embed_chunks(emb, chunk_selector.build_chunks(p))     # what Stage 3 does for the same paper
    assert emb.calls == [12]                                             # no second encode: it came from the cache


def test_papers_that_stage_3_would_not_embed_are_skipped(monkeypatch):
    emb = FakeEmbedder()
    monkeypatch.setattr(chunk_selector, "get_embedder", lambda: emb)
    patch_db(monkeypatch, {"short": paper(chunk_selector.DEFAULT_TOP_K, pid="short"), "abstract": paper(12, full_text=False, pid="abstract")})
    assert warmup.warm_paper("short") == 0                               # at most 5 chunks: all are read, nothing is embedded
    assert warmup.warm_paper("abstract") == 0                            # no usable full text
    assert warmup.warm_paper("unknown") == 0                             # not in the database
    assert emb.calls == []


def test_the_warmer_embeds_every_submitted_paper_and_finish_waits_for_them(monkeypatch):
    emb = FakeEmbedder()
    monkeypatch.setattr(chunk_selector, "get_embedder", lambda: emb)
    patch_db(monkeypatch, {f"p{i}": paper(10 + i, pid=f"p{i}") for i in range(4)})
    w = warmup.ChunkWarmer()
    for i in range(4):
        w.submit(f"p{i}")
    assert w.finish(timeout=10) is True
    assert sorted(emb.calls) == [10, 11, 12, 13] and w.papers == 4 and w.chunks == 46


def test_a_failing_paper_never_raises_and_the_others_still_run(monkeypatch):
    emb = FakeEmbedder()
    monkeypatch.setattr(chunk_selector, "get_embedder", lambda: emb)
    good = paper(10, pid="good")

    def get(ids):
        if ids == ["bad"]:
            raise RuntimeError("database down")
        return [good]
    monkeypatch.setattr(warmup.db_service, "get_papers_by_ids", get)
    w = warmup.ChunkWarmer()
    w.submit("bad")
    w.submit("good")
    assert w.finish(timeout=10) is True
    assert w.papers == 1 and emb.calls == [10]


def test_finish_gives_up_after_the_timeout_and_cancels_what_has_not_started(monkeypatch):
    release = threading.Event()
    started = []

    def slow(paper_id):
        started.append(paper_id)
        release.wait(5)
        return 1
    monkeypatch.setattr(warmup, "warm_paper", slow)
    w = warmup.ChunkWarmer()
    for i in range(3):
        w.submit(f"p{i}")
    t0 = time.time()
    assert w.finish(timeout=0.3) is False and time.time() - t0 < 2
    release.set()
    time.sleep(0.2)
    assert started == ["p0"]                                             # p1 and p2 were cancelled before they started


def test_the_switches_turn_the_warm_up_off(monkeypatch):
    emb = FakeEmbedder()
    monkeypatch.setattr(chunk_selector, "get_embedder", lambda: emb)
    patch_db(monkeypatch, {"p1": paper(12)})
    monkeypatch.setenv("STAGE3_WARM_CHUNKS", "false")
    w = warmup.ChunkWarmer()
    assert w.enabled is False
    w.submit("p1")
    assert w.finish() is True and emb.calls == []
    monkeypatch.setenv("STAGE3_WARM_CHUNKS", "true")
    monkeypatch.setenv("CHUNK_EMBED_CACHE", "false")                    # without the cache there is nothing to fill
    assert warmup.ChunkWarmer().enabled is False


def test_the_wait_setting_is_forgiving(monkeypatch):
    for raw, want in (("", 180.0), ("x", 180.0), ("-5", 0.0), ("0", 0.0), ("45", 45.0)):
        monkeypatch.setenv("STAGE3_WARM_WAIT_SECONDS", raw)
        assert warmup.wait_seconds() == want


# ---------------------------------------------------------------------------------------------------------------------------- parser
def test_the_parser_calls_back_for_each_paper_as_soon_as_it_is_done_not_at_the_end_of_the_batch():
    agent = PaperRetrievalAgent.__new__(PaperRetrievalAgent)
    events = []

    async def one(paper_id):
        await asyncio.sleep({"a": 0.01, "b": 0.15, "c": 0.01}[paper_id])
        events.append(("parsed", paper_id))
        return None if paper_id == "c" else SimpleNamespace(retrieved_paper_id=paper_id)
    agent._parse_single_paper = one

    def done(paper_id):
        events.append(("callback", paper_id))
    result = asyncio.run(agent.parse_papers(["a", "b", "c"], on_paper_done=done))
    assert [r.retrieved_paper_id for r in result] == ["a", "b"]
    assert ("callback", "c") not in events                                # a paper that gave no result is not reported
    assert events.index(("callback", "a")) < events.index(("parsed", "b"))   # a was reported while b was still being parsed


def test_a_failing_callback_does_not_break_the_parser():
    agent = PaperRetrievalAgent.__new__(PaperRetrievalAgent)

    async def one(paper_id):
        return SimpleNamespace(retrieved_paper_id=paper_id)
    agent._parse_single_paper = one

    def broken(paper_id):
        raise ValueError("boom")
    assert len(asyncio.run(agent.parse_papers(["a", "b"], on_paper_done=broken))) == 2
    assert len(asyncio.run(agent.parse_papers(["a", "b"]))) == 2          # and no callback is the old behaviour


# ----------------------------------------------------------------------------------------------------------------------- aspect split
def sqs(n=3):
    return [SimpleNamespace(id=f"s{i}", main_topic=f"What is topic {i}?", detail_questions=[f"detail {i}"]) for i in range(1, n + 1)]


def test_the_aspect_warm_up_splits_every_sub_question_like_stage_3_and_wait_lets_it_finish(monkeypatch):
    calls = []

    def flatten(details, sq_id, topic):
        time.sleep(0.05)
        calls.append((sq_id, tuple(details), topic))
        return [], {}
    monkeypatch.setattr(detail_aspects, "flatten_aspects", flatten)
    assert warmup.start_aspects("q-warm", sqs()) is True
    warmup.wait_aspects("q-warm", timeout=5)
    assert sorted(calls) == [("s1", ("detail 1",), "topic 1"), ("s2", ("detail 2",), "topic 2"), ("s3", ("detail 3",), "topic 3")]   # the cleaned topic, as in Stage 3


def test_a_failing_split_never_raises_and_the_others_still_run(monkeypatch):
    calls = []

    def flatten(details, sq_id, topic):
        if sq_id == "s2":
            raise RuntimeError("groq down")
        calls.append(sq_id)
        return [], {}
    monkeypatch.setattr(detail_aspects, "flatten_aspects", flatten)
    assert warmup.start_aspects("q-fail", sqs()) is True
    warmup.wait_aspects("q-fail", timeout=5)
    assert sorted(calls) == ["s1", "s3"]


def test_the_aspect_switch_and_a_wait_without_a_start(monkeypatch):
    monkeypatch.setattr(detail_aspects, "flatten_aspects", lambda *a: pytest.fail("must not run"))
    monkeypatch.setenv("STAGE3_WARM_ASPECTS", "false")
    assert warmup.start_aspects("q-off", sqs()) is False
    t0 = time.time()
    warmup.wait_aspects("never-started", timeout=5)                      # returns at once
    assert time.time() - t0 < 1
    monkeypatch.setenv("STAGE3_WARM_ASPECTS", "true")
    assert warmup.start_aspects("q-empty", []) is False
