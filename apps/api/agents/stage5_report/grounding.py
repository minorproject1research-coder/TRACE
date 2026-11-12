"""Entailment check of a Stage 5 sentence against the evidence of its claims. The model layer behind the deterministic checks in validators.py.

Same fall-through as Stage 4's fact checker (fact_checker.py): the NLI model is the fast path, the LLM judge re-checks what the NLI model rejects,
and every failure counts as "not supported" (fail closed).

  1. premises = their concatenation (claim wordings first, then quotes) and then each evidence text on its own, one NLI pair at a time with an early
     stop; hypothesis = the sentence without its leading attribution ("One study reports that X" -> "X"; the quote does not say "one study reports").
  2. any premise with contradiction >= STAGE5_CONTRA_MIN (0.5)          -> hard reject, the judge is NOT asked
  3. any premise with entailment    >= STAGE5_ENTAIL_MIN (0.5)          -> accept (via "nli")
  4. otherwise ONE judge call on the concatenated evidence; accepted only when supports is true and confidence >= STAGE5_JUDGE_MIN (0.7) (via "judge")
  5. a judge error, an NLI error with no judge acceptance, no evidence                                      -> reject

`nli` and `judge` are injectable: nli(pairs: list[(premise, hypothesis)]) -> list[{"contradiction","entailment","neutral"}] (the signature of
stage4_factcheck.common.nli_probs) and judge(claim, quote) -> {"supports": bool, "confidence": float, "reason": str} (the signature of
stage4_factcheck.judge.judge_support, called with claim = the sentence, quote = the evidence). The defaults are imported LAZILY inside the call,
so importing this module loads no model, opens no connection and does not even import sentence-transformers.

Thresholds are read from the environment at call time. `stats()` gives counters for the telemetry; `entails` also returns the counts of the call.
"""
import os
import re
import threading
from typing import Callable, Optional

from apps.api.agents.stage5_report import hedging, validators

DEFAULT_ENTAIL_MIN = 0.5
DEFAULT_CONTRA_MIN = 0.5
DEFAULT_JUDGE_MIN = 0.7
DEFAULT_MAX_PREMISES = 8            # NLI costs 1 to 1.7 s per pair on the laptop CPU: at most this many single premises (+ the concatenation)
DEFAULT_MAX_CHARS = 2000            # a concatenated premise is cut here (the model window is about 512 tokens anyway)

_lock = threading.Lock()
_nli_lock = threading.Lock()
_STATS: dict = {}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def entail_min() -> float:
    return _env_float("STAGE5_ENTAIL_MIN", DEFAULT_ENTAIL_MIN)


def contra_min() -> float:
    return _env_float("STAGE5_CONTRA_MIN", DEFAULT_CONTRA_MIN)


def judge_min() -> float:
    return _env_float("STAGE5_JUDGE_MIN", DEFAULT_JUDGE_MIN)


def max_premises() -> int:
    try:
        return max(1, int(os.getenv("STAGE5_NLI_MAX_PREMISES", str(DEFAULT_MAX_PREMISES))))
    except ValueError:
        return DEFAULT_MAX_PREMISES


def max_chars() -> int:
    try:
        return max(200, int(os.getenv("STAGE5_NLI_MAX_CHARS", str(DEFAULT_MAX_CHARS))))
    except ValueError:
        return DEFAULT_MAX_CHARS


def _bump(**kw) -> None:
    with _lock:
        for k, v in kw.items():
            _STATS[k] = _STATS.get(k, 0) + v


def stats() -> dict:
    """Counters since the last reset: calls, accepted_nli, accepted_judge, rejected, contradiction_rejects, nli_pairs, judge_calls, nli_errors, judge_errors."""
    with _lock:
        return dict(_STATS)


def reset_stats() -> None:
    with _lock:
        _STATS.clear()


# ------------------------------------------------------------------------------------------------------------------ default models (lazy)
def _default_nli() -> Callable:
    from apps.api.agents.stage4_factcheck.common import nli_probs
    return nli_probs


def _default_judge() -> Callable:
    from apps.api.agents.stage4_factcheck.judge import judge_support
    return judge_support


# ------------------------------------------------------------------------------------------------------------------ the check
def _premises(evidence_texts: list[str]) -> tuple[list[str], str]:
    seen, singles = set(), []
    for t in evidence_texts or []:
        t = re.sub(r"\s+", " ", t or "").strip()
        if t and t not in seen:
            seen.add(t)
            singles.append(t)
    singles = singles[:max_premises()]
    joined = " ".join(singles)[:max_chars()]
    return singles, joined


def entails(text: str, evidence_texts: list, *, nli: Optional[Callable] = None, judge: Optional[Callable] = None) -> tuple[bool, dict]:
    """(ok, detail). `detail` always has: ok, via ("nli" | "judge" | None), reason, entailment and contradiction (best over the premises, None when
    the NLI model could not be used), hypothesis, premises (count), nli_pairs, judge_calls, and judge / nli_error / judge_error when they apply."""
    detail: dict = {"ok": False, "via": None, "reason": "", "entailment": None, "contradiction": None, "hypothesis": "", "premises": 0,
                    "nli_pairs": 0, "judge_calls": 0}
    _bump(calls=1)
    singles, joined = _premises(evidence_texts)
    hyp = hedging.strip_attribution(text or "")
    detail["hypothesis"] = hyp
    detail["premises"] = len(singles)
    if not singles or not hyp.strip():
        detail["reason"] = "no evidence text to check the sentence against" if not singles else "empty sentence"
        _bump(rejected=1)
        return False, detail

    # 1. NLI: the concatenation of all the evidence first (one pair: a sentence that merges several claims is entailed by their sum, never by one
    #    of them), the single premises one at a time only when that did not decide (a batch is padded to its longest text and costs several times
    #    more on the CPU). Stops at the first premise that contradicts (hard reject) or entails (accept).
    candidates = ([joined] if len(singles) > 1 else []) + list(singles)
    ent = con = 0.0
    try:
        nli_fn = nli or _default_nli()
        for premise in candidates:
            with _nli_lock:                          # one NLI call at a time: three sections checking at once only oversubscribe the CPU threads
                probs = nli_fn([(premise, hyp)])
            if len(probs) != 1:
                raise ValueError(f"NLI returned {len(probs)} results for 1 pair")
            detail["nli_pairs"] += 1
            _bump(nli_pairs=1)
            ent = max(ent, float(probs[0].get("entailment", 0.0)))
            con = max(con, float(probs[0].get("contradiction", 0.0)))
            detail["entailment"], detail["contradiction"] = ent, con
            if con >= contra_min():
                detail["reason"] = f"the cited evidence contradicts the sentence (contradiction {con:.2f})"
                _bump(rejected=1, contradiction_rejects=1)
                return False, detail
            if ent >= entail_min():
                detail.update(ok=True, via="nli", reason=f"entailed by the cited evidence (entailment {ent:.2f})")
                _bump(accepted_nli=1)
                return True, detail
    except Exception as e:                                   # the NLI model failed: fall through to the judge, never accept without a check
        detail["nli_error"] = f"{type(e).__name__}: {e}"
        _bump(nli_errors=1)

    # 2. the judge re-checks what NLI did not accept
    detail["judge_calls"] = 1
    _bump(judge_calls=1)
    try:
        judge_fn = judge or _default_judge()
        v = judge_fn(hyp, joined)
        supports = bool(v.get("supports"))
        conf = float(v.get("confidence", 0.0))
        detail["judge"] = {"supports": supports, "confidence": conf, "reason": str(v.get("reason", ""))}
        if str(v.get("reason", "")).startswith("judge failed"):
            detail["judge_error"] = str(v.get("reason"))
            _bump(judge_errors=1)
        if supports and conf >= judge_min():
            detail.update(ok=True, via="judge", reason=f"the judge accepted it (confidence {conf:.2f})")
            _bump(accepted_judge=1)
            return True, detail
    except Exception as e:
        detail["judge_error"] = f"{type(e).__name__}: {e}"
        _bump(judge_errors=1)
    ent, con = detail["entailment"], detail["contradiction"]
    if "judge_error" in detail:
        detail["reason"] = "the sentence could not be verified against the cited evidence (the checker failed)"
    elif ent is not None:
        detail["reason"] = f"not supported by the cited claims (entailment {ent:.2f}); the judge did not accept it either"
    else:
        detail["reason"] = "not supported by the cited claims (the judge did not accept it)"
    _bump(rejected=1)
    return False, detail


def reason_from_detail(detail: dict) -> str:
    """The reason string for the retry prompt (the writer sees only this, never raw scores of other sentences)."""
    r = detail.get("reason") or "not supported by the cited claims"
    j = (detail.get("judge") or {}).get("reason")
    if j and not detail.get("ok") and detail.get("via") is None and "failed" not in str(j)[:12]:
        r += f" (judge: {j})"
    return r


def make_check(nli: Optional[Callable] = None, judge: Optional[Callable] = None) -> Callable:
    """The default `check(text, claim_ids, job) -> list[str]` of the writer: the deterministic checks first (free), the entailment check only for
    a sentence that passed them (it costs NLI time and possibly a judge call). Empty list = the sentence passed everything."""
    def check(text, claim_ids, job) -> list[str]:
        reasons = validators.check_sentence(text, claim_ids, job)
        if reasons:
            return reasons
        ok, detail = entails(text, validators.evidence_texts(job, claim_ids), nli=nli, judge=judge)
        return [] if ok else [reason_from_detail(detail)]
    return check


__all__ = ["entails", "make_check", "reason_from_detail", "stats", "reset_stats"]
