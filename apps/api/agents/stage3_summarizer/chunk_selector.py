# apps/api/agents/stage3_summarizer/chunk_selector.py
"""Picks the passages of a paper that a digest reads.

Embedding the chunks is the whole cost of Stage 3 preparation (about 6 chunks per second on the CPU: 3 to 9 minutes per run), and the same
paper is embedded again for every sub-question that keeps it and again in every rerun. The embeddings of a paper are therefore stored on
disk, keyed by the embedding model, the chunking version and the exact chunk texts, so a changed paper or chunking never reuses an old
vector (planned item B5).
  CHUNK_EMBED_CACHE=true|false      default true
  CHUNK_EMBED_CACHE_DIR=...         default .cache/chunk_embeddings
"""
import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path

import numpy as np

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

logger = logging.getLogger(__name__)

SKIP = re.compile(r"reference|bibliograph|acknowledg|appendix|funding|conflict of interest", re.I)

# --- Constants ---
DETAIL_CHUNKS_PER_DETAIL = 2          # top chunks per detail question
MAX_CHUNKS_TOTAL = 9                  # cap on total chunks per source after union
NON_PROSE_ALPHA_RATIO = 0.60          # min alphabetic char ratio for prose
NON_PROSE_PIPE_THRESHOLD = 5          # max "|" chars before treating as table/figure caption
EMBED_MODEL_ID = "BAAI/bge-base-en-v1.5"
CHUNKING_VERSION = 1                  # raise when _split / build_chunks change what a chunk is
DEFAULT_TOP_K = 5                     # select_chunks reads every chunk of a source that has at most this many (so nothing is embedded for it)


def _split(text: str, size: int = 300) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def _clean_topic(main_topic: str) -> str:
    """Strip leading 'What is' and trailing '?' from main topic."""
    t = main_topic.strip()
    t = re.sub(r"^what\s+is\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\?$", "", t).strip()
    return t


def _is_prose(chunk: str) -> bool:
    """Heuristic: keep chunks that look like prose (mostly alphabetic, not tables/captions)."""
    if not chunk:
        return False
    alpha = sum(1 for c in chunk if c.isalpha())
    total = len(chunk)
    if total == 0:
        return False
    if alpha / total < NON_PROSE_ALPHA_RATIO:
        return False
    if chunk.count("|") > NON_PROSE_PIPE_THRESHOLD:
        return False
    return True


def build_chunks(paper: dict) -> list[str]:
    chunks = []
    for s in paper.get("sections") or []:
        if SKIP.search(s.get("heading") or ""):
            continue
        chunks += _split(s.get("text") or s.get("content") or "")
    if not chunks and paper.get("full_text"):
        chunks = _split(paper["full_text"])
    if not chunks and paper.get("abstract"):
        chunks = [paper["abstract"]]
    return [c for c in chunks if len(c.split()) >= 30]


def _cache_enabled() -> bool:
    return os.getenv("CHUNK_EMBED_CACHE", "true").strip().lower() not in ("0", "false", "no", "off")


def _cache_path(chunks: list[str]) -> Path:
    h = hashlib.sha256(f"{EMBED_MODEL_ID}|chunking-v{CHUNKING_VERSION}|{len(chunks)}|".encode())
    for c in chunks:
        h.update(c.encode("utf-8", "replace"))
        h.update(b"\x1f")                                           # separator, so ["ab", "c"] and ["a", "bc"] differ
    return Path(os.getenv("CHUNK_EMBED_CACHE_DIR", ".cache/chunk_embeddings")) / f"{h.hexdigest()}.npy"


def embed_chunks(model, chunks: list[str]) -> np.ndarray:
    """Normalised embeddings of the chunks, from the disk cache when this exact list was embedded before."""
    if not _cache_enabled():
        return model.encode(chunks, normalize_embeddings=True)
    path = _cache_path(chunks)
    try:
        cached = np.load(path)
        if cached.shape[0] == len(chunks):
            return cached
    except FileNotFoundError:
        pass
    except Exception as e:                                          # a damaged file must cost a recomputation, never the run
        logger.warning("chunk embedding cache file %s is not usable (%s); embedding again", path.name, type(e).__name__)
    d = np.asarray(model.encode(chunks, normalize_embeddings=True))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            np.save(f, d)
        os.replace(tmp, path)                                       # atomic: a reader never sees half a file
    except OSError as e:
        logger.warning("chunk embedding cache write failed: %s", e)
    return d


def select_chunks(
    sub_question: str,
    chunks: list[str],
    top_k: int = DEFAULT_TOP_K,
    *,
    detail_questions: list[str] | None = None,
    main_topic: str | None = None,
) -> list[tuple[int, str]]:
    """
    Returns [(chunk_id, text)] for the top chunks.
    
    Selection:
    - Always include top_k chunks by similarity to sub_question.
    - If detail_questions and main_topic provided, also select DETAIL_CHUNKS_PER_DETAIL
      chunks per detail using topic-prefixed query.
    - Union of both sets, deduplicated by chunk_id, capped at MAX_CHUNKS_TOTAL.
    - Sub-question top chunks preferred when cap bites.
    """
    if len(chunks) <= top_k:
        return list(enumerate(chunks))

    model = get_embedder()
    
    # 1. Sub-question based selection (always done)
    q = model.encode([sub_question], normalize_embeddings=True)[0]
    d = embed_chunks(model, chunks)
    sq_sims = d @ q
    sq_top = sorted(range(len(chunks)), key=lambda i: sq_sims[i], reverse=True)[:top_k]
    
    # 2. Detail-targeted selection (optional)
    detail_extra = set()
    if detail_questions and main_topic:
        cleaned_topic = _clean_topic(main_topic)
        for detail in detail_questions:
            prefixed = f"{cleaned_topic}: {detail}"
            dq = model.encode([prefixed], normalize_embeddings=True)[0]
            det_sims = d @ dq
            det_ranked = sorted(range(len(chunks)), key=lambda i: det_sims[i], reverse=True)
            for idx in det_ranked:
                if len(detail_extra) >= DETAIL_CHUNKS_PER_DETAIL:
                    break
                if not _is_prose(chunks[idx]):
                    continue
                detail_extra.add(idx)
    
    # 3. Union with preference for sub-question top chunks, then cap
    selected_ids = list(sq_top) + [i for i in detail_extra if i not in sq_top]
    if len(selected_ids) > MAX_CHUNKS_TOTAL:
        selected_ids = selected_ids[:MAX_CHUNKS_TOTAL]
    
    return [(i, chunks[i]) for i in sorted(selected_ids)]


def select_more_chunks(chunks: list[str], queries: list[str], exclude: set[int], per_query: int = 2, *, main_topic: str | None = None) -> list[tuple[int, str]]:
    """Loop 2, step 1: for each query (an uncovered aspect), the `per_query` best prose chunks that the digest has NOT read yet.
    exclude = chunk ids already given to a digest of this source. Returns [(chunk_id, text)] sorted by chunk id (deduplicated)."""
    if not chunks or not queries:
        return []
    model = get_embedder()
    d = embed_chunks(model, chunks)
    topic = _clean_topic(main_topic) if main_topic else ""
    picked: set[int] = set()
    for text in queries:
        q = model.encode([f"{topic}: {text}" if topic else text], normalize_embeddings=True)[0]
        sims = d @ q
        taken = 0
        for idx in sorted(range(len(chunks)), key=lambda i: sims[i], reverse=True):
            if taken >= per_query:
                break
            if idx in exclude or idx in picked or not _is_prose(chunks[idx]):
                continue
            picked.add(idx)
            taken += 1
    return [(i, chunks[i]) for i in sorted(picked)]
