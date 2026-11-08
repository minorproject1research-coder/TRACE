"""Precision and recall of the three Stage 4 decisions on the labeled set (reports/stage4_eval_set.json): is it the same claim (merge), does the
quote support the claim (support), do two sources directly contradict (conflict). Also shows how well the cheap gates (embedding similarity, NLI)
separate the labels, because those thresholds were never tuned (handoff report, task 5).

Real judge calls (Groq, cached in .cache/stage4_judge, so a rerun is free); NLI on the CPU only with --nli (about 1.7 s per pair).
Pairs whose judge call FAILED (rate limit) are left out and counted; a number from a run with failures is printed with a warning.

  python tests/stage4_eval.py [--nli]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder  # noqa: E402
from apps.api.agents.stage4_factcheck import contradiction_detector as cd, fact_checker as fc, judge  # noqa: E402

DATA = json.loads((ROOT / "reports" / "stage4_eval_set.json").read_text(encoding="utf-8"))
NLI = "--nli" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None      # --only conflict: skip the other two sets (saves Groq calls)
if ONLY:
    for _k in ("merge", "support", "conflict"):
        if _k != ONLY:
            DATA[_k] = []


def prf(rows, pred_key="pred", label_key="label"):
    tp = sum(1 for r in rows if r[pred_key] and r[label_key])
    fp = sum(1 for r in rows if r[pred_key] and not r[label_key])
    fn = sum(1 for r in rows if not r[pred_key] and r[label_key])
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return f"precision {p:.2f} recall {r:.2f} (tp {tp}, fp {fp}, fn {fn})"


def call(fn, *a):
    """(result, failed) - a judge call that failed closed is not a prediction."""
    s0 = judge.stats()
    out = fn(*a)
    s1 = judge.stats()
    return out, (s1["failures"] - s0["failures"] + s1["skipped"] - s0["skipped"]) > 0


emb = get_embedder()
failed_total = 0

# ---------------------------------------------------------------------------------------------------------------- merge
print("=== MERGE: judge_same_claim, and how many different-claim pairs the similarity thresholds would merge")
rows, sims = [], []
for m in DATA["merge"]:
    a, b = emb.encode([m["a"], m["b"]], normalize_embeddings=True)
    sims.append({"label": m["same"], "sim": float(a @ b)})
    pred, failed = call(judge.judge_same_claim, m["a"], m["b"])
    failed_total += failed
    if not failed:
        rows.append({"label": m["same"], "pred": pred, "sim": float(a @ b), "m": m})
print(f"{len(DATA['merge'])} pairs, {sum(r['label'] for r in sims)} are the same claim; {len(rows)} judged without a failure")
print("judge:", prf(rows))
for th in (0.80, 0.90, 0.95, 0.97, 0.98):
    above = [r for r in sims if r["sim"] >= th]
    print(f"  similarity >= {th:.2f}: {len(above):2d} pairs, of which {sum(1 for r in above if not r['label'])} are DIFFERENT claims (a merge without the judge would be wrong), "
          f"{sum(1 for r in above if r['label'])} are the same")
print("  same-claim pairs: similarity", sorted(round(r["sim"], 2) for r in sims if r["label"]))
for r in rows:
    if r["pred"] != r["label"]:
        print(f"  judge wrong (label {r['label']}, sim {r['sim']:.2f}):\n    A: {r['m']['a'][:120]}\n    B: {r['m']['b'][:120]}")

# --------------------------------------------------------------------------------------------------------------- support
print("\n=== SUPPORT: does the quote support the claim?")
rows = []
for s in DATA["support"]:
    v, failed = call(judge.judge_support, s["claim"], s["quote"])
    failed_total += failed
    if failed:
        continue
    rows.append({"label": s["supports"], "pred": v["supports"] and v["confidence"] >= fc.SUPPORT_JUDGE_MIN, "conf": v["confidence"], "s": s})
print(f"{len(rows)} pairs, {sum(r['label'] for r in rows)} supported")
print(f"judge (supports and confidence >= {fc.SUPPORT_JUDGE_MIN}):", prf(rows))
if NLI:
    from apps.api.agents.stage4_factcheck.common import nli_probs
    probs = nli_probs([(s["quote"], s["claim"]) for s in DATA["support"]])
    nrows = [{"label": s["supports"], "pred": p["entailment"] >= fc.ENTAIL_MIN, "ent": p["entailment"]} for s, p in zip(DATA["support"], probs)]
    print(f"NLI (entailment >= {fc.ENTAIL_MIN}):", prf(nrows))
for r in rows:
    if r["pred"] != r["label"]:
        print(f"  judge wrong (label {r['label']}, conf {r['conf']:.2f}):\n    CLAIM: {r['s']['claim'][:130]}\n    QUOTE: {r['s']['quote'][:130]}")

# -------------------------------------------------------------------------------------------------------------- conflict
print("\n=== CONFLICT: judge_conflict(claim A, quote of B, claim B)")
rows, gates = [], []
for c in DATA["conflict"]:
    qa = emb.encode([c["a"], c["quote_b"]], normalize_embeddings=True)
    gates.append({"label": c["conflicts"], "gate": float(qa[0] @ qa[1]), "c": c})
    v, failed = call(judge.judge_conflict, c["a"], c["quote_b"], c["b"])
    failed_total += failed
    if failed:
        continue
    rows.append({"label": c["conflicts"], "v": v, "gate": float(qa[0] @ qa[1]), "c": c})
print(f"{len(DATA['conflict'])} pairs, {sum(r['label'] for r in gates)} real conflicts; {len(rows)} judged without a failure")
for t in (0.5, 0.7, 0.85, 0.95):
    for r in rows:
        r["pred"] = r["v"]["conflicts"] and r["v"]["same_aspect"] and r["v"]["confidence"] >= t
    print(f"judge, confidence >= {t}:", prf(rows))
for r in rows:
    r["pred"] = r["v"]["conflicts"] and r["v"]["same_aspect"] and r["v"]["confidence"] >= cd.JUDGE_MIN
    if r["pred"] != r["label"]:
        print(f"  wrong at JUDGE_MIN {cd.JUDGE_MIN} (label {r['label']}, confidence {r['v']['confidence']:.2f}): {r['v']['reason'][:110]}\n    A: {r['c']['a'][:110]}\n    B: {r['c']['b'][:110]}")
neg = sorted(r["gate"] for r in gates if not r["label"])
print("topic gate (quote B vs claim A cosine): real conflicts", sorted(round(r["gate"], 2) for r in gates if r["label"]),
      "| non-conflicts min/median/max", [round(neg[0], 2), round(neg[len(neg) // 2], 2), round(neg[-1], 2)],
      f"| gate {cd.QUOTE_CLAIM_SIM}: passes {sum(1 for r in gates if r['gate'] >= cd.QUOTE_CLAIM_SIM and r['label'])} real conflicts, {sum(1 for r in gates if r['gate'] >= cd.QUOTE_CLAIM_SIM and not r['label'])} non-conflicts")
if NLI:
    probs = nli_probs([(r["c"]["quote_b"], r["c"]["a"]) for r in gates])
    print("NLI contradiction probability: real conflicts", sorted(round(p["contradiction"], 2) for p, r in zip(probs, gates) if r["label"]),
          "| non-conflicts at or above", cd.CONTRADICT_MIN, ":", sum(1 for p, r in zip(probs, gates) if not r["label"] and p["contradiction"] >= cd.CONTRADICT_MIN), "of", len(neg))

if failed_total:
    print(f"\nWARNING: {failed_total} judge call(s) failed (rate limit) and were left out; run again later (answers already received are cached).")
