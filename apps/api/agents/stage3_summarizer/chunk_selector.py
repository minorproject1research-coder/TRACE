# apps/api/agents/stage3_summarizer/chunk_selector.py
import re
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

SKIP = re.compile(r"reference|bibliograph|acknowledg|appendix|funding|conflict of interest", re.I)


def _split(text: str, size: int = 300) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


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


def select_chunks(sub_question: str, chunks: list[str], top_k: int = 5) -> list[tuple[int, str]]:
    """Returns [(chunk_id, text)] for the top_k chunks most similar to the sub-question."""
    if len(chunks) <= top_k:
        return list(enumerate(chunks))
    model = get_embedder()
    q = model.encode([sub_question], normalize_embeddings=True)[0]
    d = model.encode(chunks, normalize_embeddings=True)
    sims = d @ q
    top = sorted(range(len(chunks)), key=lambda i: sims[i], reverse=True)[:top_k]
    return [(i, chunks[i]) for i in sorted(top)]