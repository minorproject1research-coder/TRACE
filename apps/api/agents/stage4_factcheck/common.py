import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
from pathlib import Path

import numpy as np
from sentence_transformers import CrossEncoder

NLI_MODEL = os.getenv("NLI_MODEL", "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli")
_nli = None
_nli_lock = threading.Lock()


def clean_text(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    t = t.replace("\u2010", "-").replace("\u2011", "-").replace("\u2019", "'")
    t = re.sub(r"[\u00a0\u202f\u2009\u200b]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _model():
    global _nli
    if _nli is None:
        with _nli_lock:                         # two threads (the preload and Stage 4) must not both load 1.7 GB
            if _nli is None:
                _nli = CrossEncoder(NLI_MODEL)
    return _nli


def preload_nli() -> None:
    """Load the NLI model in a background thread (it takes 10 to 60 s) so that it is ready when Stage 4 starts; called at the start of a run
    that has Stage 4 switched on. A failure here is ignored: Stage 4 loads the model itself and reports its own error."""
    def load():
        try:
            _model()
        except Exception:
            pass
    if _nli is None:
        threading.Thread(target=load, name="nli-preload", daemon=True).start()


def _label_index(m) -> dict:
    cfg = getattr(m, "config", None) or m.model.config
    idx = {str(l).lower(): int(i) for i, l in cfg.id2label.items()}
    missing = {"contradiction", "entailment", "neutral"} - set(idx)
    if missing:
        raise RuntimeError(f"Unexpected NLI labels {cfg.id2label}; missing {missing}")
    return idx


def _nli_cache_on() -> bool:
    return os.getenv("NLI_CACHE", "true").strip().lower() not in ("0", "false", "no", "off")


def _nli_cache_path(premise: str, hypothesis: str) -> Path:
    key = hashlib.sha256(f"{NLI_MODEL}|{premise}|{hypothesis}".encode("utf-8")).hexdigest()
    return Path(os.getenv("NLI_CACHE_DIR", ".cache/nli")) / key[:2] / f"{key}.json"


def nli_probs(pairs: list[tuple[str, str]]) -> list[dict]:
    """pairs = [(premise, hypothesis)] -> [{"contradiction": p, "entailment": p, "neutral": p}]

    The model is deterministic, so every answer is cached on disk (NLI_CACHE, default on; .cache/nli): a second Stage 4 run on the same quotes
    and claims (a repeated test question, a rerun on stored data) costs no CPU time. The CPU time of this model is most of Stage 4."""
    if not pairs:
        return []
    cleaned = [(clean_text(p), clean_text(h)) for p, h in pairs]
    results: list[dict | None] = [None] * len(cleaned)
    todo = []
    for i, (p, h) in enumerate(cleaned):
        if _nli_cache_on():
            try:
                results[i] = json.loads(_nli_cache_path(p, h).read_text(encoding="utf-8"))
                continue
            except (OSError, ValueError):
                pass
        todo.append(i)
    if todo:
        m = _model()
        idx = _label_index(m)
        out = np.asarray(m.predict([cleaned[i] for i in todo], batch_size=16), dtype=float)
        if out.ndim == 1:
            out = out.reshape(1, -1)
        if np.all((out >= 0) & (out <= 1)) and np.allclose(out.sum(axis=1), 1.0, atol=1e-3):
            p = out
        else:
            z = out - out.max(axis=1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(axis=1, keepdims=True)
        for i, row in zip(todo, p):
            results[i] = {k: float(row[idx[k]]) for k in ("contradiction", "entailment", "neutral")}
            if _nli_cache_on():
                path = _nli_cache_path(*cleaned[i])
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(results[i], f)
                    os.replace(tmp, path)
                except OSError:
                    pass                                  # a cache that cannot be written must never break Stage 4
    return results  # type: ignore[return-value]


def doc_key(title: str | None, source_id) -> str:
    """Normalized title so the same document found as web + paper counts once."""
    t = re.split(r"\s[|\-–]\s", title or "")[0].lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return re.sub(r"\s+", " ", t).strip() or str(source_id)