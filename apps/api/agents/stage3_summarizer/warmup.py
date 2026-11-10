"""Stage 3 work that does not need Stage 3, done earlier (2026-11-10, run 33: Stage 3 preparation took 2 minutes right after 4 minutes of PDF
parsing, and the CPU of this machine was idle while the model host parsed).

Both helpers only fill caches that Stage 3 reads anyway, so the results are identical with or without them: when something here is late,
fails or is switched off, Stage 3 does the same work itself, a little later.

  STAGE3_WARM_CHUNKS=true      embed the chunks of every paper as soon as it is parsed (needs CHUNK_EMBED_CACHE=true, the default)
  STAGE3_WARM_WAIT_SECONDS=180 how long the end of the parse step waits for the last embeddings (0 = do not wait)
  STAGE3_WARM_ASPECTS=true     split the detail questions into aspects (Groq, cached) right after the planner instead of in Stage 3
"""
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, wait

from apps.api.agents.stage3_summarizer import chunk_selector, detail_aspects
from apps.api.services import db_service

logger = logging.getLogger("apps.api.agents.stage3_summarizer")


def _flag(name: str) -> bool:
    return os.getenv(name, "true").strip().lower() not in ("0", "false", "no", "off")


def chunks_enabled() -> bool:
    return _flag("STAGE3_WARM_CHUNKS") and chunk_selector._cache_enabled()


def aspects_enabled() -> bool:
    return _flag("STAGE3_WARM_ASPECTS")


def wait_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("STAGE3_WARM_WAIT_SECONDS", "180")))
    except ValueError:
        return 180.0


# ------------------------------------------------------------------------------------------------------------------ chunk embeddings
def warm_paper(paper_id: str) -> int:
    """Embeds the chunks of one parsed paper into the chunk-embedding cache, exactly as Stage 3 would (same paper rows, same chunking, same
    cache key). Returns the number of chunks embedded; 0 when Stage 3 would not embed this paper (no usable full text, or so few chunks that
    all of them are read)."""
    papers = db_service.get_papers_by_ids([paper_id])
    if not papers or not papers[0].get("has_full_text"):
        return 0
    chunks = chunk_selector.build_chunks(papers[0])
    if len(chunks) <= chunk_selector.DEFAULT_TOP_K:
        return 0
    chunk_selector.embed_chunks(chunk_selector.get_embedder(), chunks)
    return len(chunks)


class ChunkWarmer:
    """One background worker that warms the papers handed to submit() (the parser calls it for every paper it has stored). Never raises."""

    def __init__(self):
        self.enabled = chunks_enabled()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stage3-warm") if self.enabled else None
        self._futures = []
        self._lock = threading.Lock()
        self.papers = 0
        self.chunks = 0

    def submit(self, paper_id: str) -> None:
        if self._pool is None:
            return
        try:
            self._futures.append(self._pool.submit(self._one, paper_id))
        except Exception:
            logger.exception("could not queue the chunk warm-up of paper %s", paper_id)

    def _one(self, paper_id: str) -> None:
        try:
            n = warm_paper(paper_id)
            with self._lock:
                self.papers += 1 if n else 0
                self.chunks += n
        except Exception as e:
            logger.warning("chunk warm-up of paper %s failed (%s); Stage 3 will embed it itself", paper_id, type(e).__name__)

    def finish(self, timeout: float | None = None) -> bool:
        """Waits for the queued papers (at most `timeout` seconds; None = wait for all) and stops the worker. True when everything was done."""
        if self._pool is None:
            return True
        done, not_done = wait(self._futures, timeout=timeout)
        for f in not_done:
            f.cancel()                                  # not started yet: Stage 3 will do it; one that runs now simply completes
        self._pool.shutdown(wait=False)
        logger.info("Stage 3 chunk warm-up: %d paper(s), %d chunk(s) embedded early%s", self.papers, self.chunks,
                    "" if not not_done else f"; {len(not_done)} paper(s) left for Stage 3")
        return not not_done


# ------------------------------------------------------------------------------------------------------------------------- aspect split
_aspect_threads: dict[str, threading.Thread] = {}
_aspect_lock = threading.Lock()


def _split_one(sq) -> None:
    try:
        detail_aspects.flatten_aspects(sq.detail_questions, sq.id, chunk_selector._clean_topic(sq.main_topic))
    except Exception as e:
        logger.warning("aspect warm-up of sub-question '%s' failed (%s); Stage 3 will split it itself", str(getattr(sq, "main_topic", ""))[:50], type(e).__name__)


def start_aspects(query_id: str, sub_questions) -> bool:
    """Starts splitting the detail questions of every sub-question into aspects (the Groq calls are cached by detail text and sub-question id,
    so Stage 3 finds the answers). Returns at once. Never raises."""
    if not aspects_enabled():
        return False
    try:
        subs = list(sub_questions)
        if not subs:
            return False

        def run():
            with ThreadPoolExecutor(max_workers=min(4, len(subs)), thread_name_prefix="stage3-aspects") as pool:
                list(pool.map(_split_one, subs))

        t = threading.Thread(target=run, daemon=True, name="stage3-aspects-warm")
        with _aspect_lock:
            _aspect_threads[query_id] = t
        t.start()
        return True
    except Exception:
        logger.exception("could not start the aspect warm-up")
        return False


def wait_aspects(query_id: str, timeout: float = 60.0) -> None:
    """Called by Stage 3 before it splits the aspects itself: lets a warm-up that is still running finish, so the same Groq calls are not
    made twice. Does nothing when no warm-up was started."""
    with _aspect_lock:
        t = _aspect_threads.pop(query_id, None)
    if t is not None:
        t.join(timeout)
