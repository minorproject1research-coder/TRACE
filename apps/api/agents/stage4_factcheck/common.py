import os
import re
import unicodedata

import numpy as np
from sentence_transformers import CrossEncoder

NLI_MODEL = os.getenv("NLI_MODEL", "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli")
_nli = None


def clean_text(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    t = t.replace("\u2010", "-").replace("\u2011", "-").replace("\u2019", "'")
    t = re.sub(r"[\u00a0\u202f\u2009\u200b]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _model():
    global _nli
    if _nli is None:
        _nli = CrossEncoder(NLI_MODEL)
    return _nli


def _label_index(m) -> dict:
    cfg = getattr(m, "config", None) or m.model.config
    idx = {str(l).lower(): int(i) for i, l in cfg.id2label.items()}
    missing = {"contradiction", "entailment", "neutral"} - set(idx)
    if missing:
        raise RuntimeError(f"Unexpected NLI labels {cfg.id2label}; missing {missing}")
    return idx


def nli_probs(pairs: list[tuple[str, str]]) -> list[dict]:
    """pairs = [(premise, hypothesis)] -> [{"contradiction": p, "entailment": p, "neutral": p}]"""
    if not pairs:
        return []
    m = _model()
    idx = _label_index(m)
    cleaned = [(clean_text(p), clean_text(h)) for p, h in pairs]
    out = np.asarray(m.predict(cleaned, batch_size=16), dtype=float)
    if out.ndim == 1:
        out = out.reshape(1, -1)
    if np.all((out >= 0) & (out <= 1)) and np.allclose(out.sum(axis=1), 1.0, atol=1e-3):
        p = out
    else:
        z = out - out.max(axis=1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(axis=1, keepdims=True)
    return [{k: float(row[idx[k]]) for k in ("contradiction", "entailment", "neutral")} for row in p]


def doc_key(title: str | None, source_id) -> str:
    """Normalized title so the same document found as web + paper counts once."""
    t = re.split(r"\s[|\-–]\s", title or "")[0].lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return re.sub(r"\s+", " ", t).strip() or str(source_id)