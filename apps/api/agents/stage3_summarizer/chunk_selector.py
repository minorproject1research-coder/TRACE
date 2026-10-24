# apps/api/agents/stage3_summarizer/chunk_selector.py
import re
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

SKIP = re.compile(r"reference|bibliograph|acknowledg|appendix|funding|conflict of interest", re.I)

# --- Constants ---
DETAIL_CHUNKS_PER_DETAIL = 2          # top chunks per detail question
MAX_CHUNKS_TOTAL = 9                  # cap on total chunks per source after union
NON_PROSE_ALPHA_RATIO = 0.60          # min alphabetic char ratio for prose
NON_PROSE_PIPE_THRESHOLD = 5          # max "|" chars before treating as table/figure caption


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


def select_chunks(
    sub_question: str,
    chunks: list[str],
    top_k: int = 5,
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
    d = model.encode(chunks, normalize_embeddings=True)
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