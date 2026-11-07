"""Chunk-embedding cache (planned item B5). Pass rule: the chunk selection is identical with and without the cache. Offline, fake model."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import chunk_selector as cs  # noqa: E402


class FakeModel:
    """Deterministic 16-dimensional embeddings from the words of a text; counts what it was asked to embed."""
    def __init__(self):
        self.encoded = 0

    def encode(self, texts, normalize_embeddings=True):
        self.encoded += len(texts)
        out = []
        for t in texts:
            v = np.zeros(16, dtype=np.float32)
            for w in t.lower().split():
                v[sum(map(ord, w)) % 16] += 1.0
            out.append(v / (np.linalg.norm(v) + 1e-8))
        return np.array(out)


def make_chunks(n=24):
    words = ["alpha", "beta", "gamma", "delta", "privacy", "attack", "defense", "model", "update", "gradient"]
    return [" ".join(words[(i + j) % len(words)] + str(i % 3) for j in range(40)) for i in range(n)]


@pytest.fixture
def model(monkeypatch, tmp_path):
    m = FakeModel()
    monkeypatch.setattr(cs, "get_embedder", lambda: m)
    monkeypatch.setenv("CHUNK_EMBED_CACHE_DIR", str(tmp_path / "emb"))
    monkeypatch.setenv("CHUNK_EMBED_CACHE", "true")
    return m


def select(chunks):
    return cs.select_chunks("privacy attack on model update", chunks, detail_questions=["defense of the model", "gradient update"],
                            main_topic="federated learning")


def test_selection_is_identical_with_and_without_the_cache(model, monkeypatch):
    chunks = make_chunks()
    monkeypatch.setenv("CHUNK_EMBED_CACHE", "false")
    without = select(chunks)
    monkeypatch.setenv("CHUNK_EMBED_CACHE", "true")
    first = select(chunks)                 # miss: computed and stored
    second = select(chunks)                # hit
    assert without == first == second


def test_second_call_does_not_embed_the_chunks_again(model):
    chunks = make_chunks()
    select(chunks)
    after_first = model.encoded
    select(chunks)
    # only the sub-question and the two detail queries are embedded again, not the 24 chunks
    assert model.encoded - after_first == 3
    assert after_first >= len(chunks)


def test_a_changed_chunk_is_embedded_again(model):
    chunks = make_chunks()
    select(chunks)
    before = model.encoded
    changed = list(chunks)
    changed[5] = changed[5] + " newly added sentence"
    select(changed)
    assert model.encoded - before >= len(changed)          # new key: the whole paper is embedded again


def test_a_damaged_cache_file_is_recomputed(model, tmp_path):
    chunks = make_chunks()
    expected = select(chunks)
    for f in (tmp_path / "emb").glob("*.npy"):
        f.write_bytes(b"not a numpy file")
    assert select(chunks) == expected


def test_a_cache_file_with_the_wrong_length_is_not_used(model, tmp_path):
    chunks = make_chunks()
    expected = select(chunks)
    for f in (tmp_path / "emb").glob("*.npy"):
        np.save(f, np.zeros((3, 16), dtype=np.float32))
    assert select(chunks) == expected


def test_unwritable_cache_dir_does_not_stop_the_selection(model, tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("CHUNK_EMBED_CACHE_DIR", str(blocker / "sub"))      # a directory below a file cannot be created
    assert select(make_chunks())


def test_chunk_boundaries_matter_for_the_key():
    a = cs._cache_path(["ab", "c"])
    b = cs._cache_path(["a", "bc"])
    assert a != b
