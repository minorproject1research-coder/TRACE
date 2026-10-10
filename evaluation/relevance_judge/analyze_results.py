"""Deeper analysis of the benchmark results (the numbers quoted in README section 10).

  python -m evaluation.relevance_judge.analyze_results            # every section
  python -m evaluation.relevance_judge.analyze_results signif     # one section

Sections: verify, invalid, missing, signif, conf, confsem, ensemble, cascade, breakdown, audit, answered, clear, latency

Reads results/<model>.jsonl (raw per-row answers) and the labeled dataset: the local dataset.jsonl if present, otherwise
the Hugging Face dataset minorproject-research/trace-relevance-judge. No model is called and nothing is written.
"""
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
RES = HERE / "results"
HF_DATASET = "minorproject-research/trace-relevance-judge"
SECTION = sys.argv[1] if len(sys.argv) > 1 else "all"


# --------------------------------------------------------------------------- data
def load_gold():
    path = HERE / "dataset.jsonl"
    if path.exists():
        return {r["id"]: r for r in (json.loads(l) for l in path.open(encoding="utf-8") if l.strip())}
    from datasets import load_dataset                                  # fall back to the published dataset
    gold = {}
    for r in load_dataset(HF_DATASET, split="test", token=False):
        r = dict(r)
        r["label"] = {"relevant": r["relevant"], "confidence": r["label_confidence"], "reason": r["label_reason"]}
        gold[r["id"]] = r
    return gold


gold = load_gold()
IDS = list(gold)
N = len(IDS)
POS = sum(g["label"]["relevant"] for g in gold.values())
NEG = N - POS

res = {}
for f in sorted(RES.glob("*.jsonl")):
    rows = {}
    for line in f.open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rows[r["id"]] = r
    res[f.stem] = rows
if not res:
    raise SystemExit(f"no result files in {RES}")

COMPLETE = [m for m, rows in res.items() if set(IDS) <= set(rows)]
PARTIAL = [m for m in res if m not in COMPLETE]


# --------------------------------------------------------------------------- helpers
def pred(m, i, thr=0.0):
    """Model's decision for row i. An unparseable / missing answer counts as 'not relevant', as in production."""
    v = res[m][i]["verdict"]
    return bool(v and v["relevant"] and v["confidence"] >= thr)


def metrics(pairs):
    tp = sum(g and p for g, p in pairs)
    fp = sum((not g) and p for g, p in pairs)
    fn = sum(g and (not p) for g, p in pairs)
    tn = sum((not g) and (not p) for g, p in pairs)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return dict(acc=(tp + tn) / len(pairs), prec=prec, rec=rec, f1=f1, spec=tn / (tn + fp) if tn + fp else 0.0,
                tp=tp, fp=fp, fn=fn, tn=tn)


def model_pairs(m, ids=IDS, thr=0.0):
    return [(gold[i]["label"]["relevant"], pred(m, i, thr)) for i in ids if i in res[m]]


def mcnemar_p(b01, b10):
    """Exact two-sided McNemar p-value from the two discordant counts."""
    n = b01 + b10
    if n == 0:
        return 1.0
    k = min(b01, b10)
    return min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)


def mcnemar(a, b, ids=IDS):
    ok = lambda m, i: pred(m, i) == gold[i]["label"]["relevant"]
    b01 = sum(1 for i in ids if ok(a, i) and not ok(b, i))
    b10 = sum(1 for i in ids if ok(b, i) and not ok(a, i))
    return b01, b10, mcnemar_p(b01, b10)


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return float("nan")
    return sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg) / (len(pos) * len(neg))


def p_rel(m, i, low_not_is_p_relevant=False):
    """Score for 'relevant': the stated confidence if the verdict is relevant, else 1 - confidence.
    With low_not_is_p_relevant, a 'not relevant' verdict with confidence <= 0.3 is read as P(relevant) (some models do this)."""
    v = res[m][i]["verdict"]
    if not v:
        return None
    if v["relevant"]:
        return v["confidence"]
    if low_not_is_p_relevant and v["confidence"] <= 0.3:
        return v["confidence"]
    return 1 - v["confidence"]


def sec(name):
    return SECTION in ("all", name)


def by_f1(models):
    return sorted(models, key=lambda m: -metrics(model_pairs(m))["f1"])


def title(text):
    print("\n" + "=" * 30, text, "=" * 30)


# --------------------------------------------------------------------------- sections
if sec("verify"):
    title("0. Per-model metrics recomputed from the raw rows")
    print(f"dataset {N} rows ({POS} relevant / {NEG} not). complete: {len(COMPLETE)} models; partial: { {m: len(res[m]) for m in PARTIAL} }")
    print(f"{'model':28s} {'rows':>4} {'acc':>6} {'prec':>6} {'rec':>6} {'F1':>6} {'rejects-irrelevant':>19} {'invalid':>7} {'errors':>6}")
    for m in by_f1(res):
        mt = metrics(model_pairs(m))
        inv = sum(1 for r in res[m].values() if r["verdict"] is None and not r["error"])
        err = sum(1 for r in res[m].values() if r["error"])
        print(f"{m:28s} {len(res[m]):4d} {mt['acc']:6.3f} {mt['prec']:6.3f} {mt['rec']:6.3f} {mt['f1']:6.3f} {mt['spec']:19.0%} {inv:7d} {err:6d}")

if sec("invalid"):
    title("1. Why were replies invalid?")
    for m in res:
        bad = [r for r in res[m].values() if r["verdict"] is None]
        if not bad:
            continue
        kinds = Counter()
        for r in bad:
            raw = r["raw"] or ""
            if r["error"]:
                kinds["error: " + str(r["error"])[:50]] += 1
            elif not raw.strip():
                kinds["empty reply (likely all tokens spent on hidden reasoning)"] += 1
            elif "<think>" in raw and "</think>" not in raw:
                kinds["unterminated <think> block"] += 1
            elif len(raw) >= 1490:
                kinds["long reply with no usable JSON (reasoning text; stored text cut at 1500 chars)"] += 1
            elif "{" not in raw:
                kinds["no JSON object in reply"] += 1
            else:
                kinds["braces but not a valid verdict (often truncated JSON)"] += 1
        print(f"\n{m}: {len(bad)} invalid of {len(res[m])}")
        for k, v in kinds.most_common():
            print(f"   {v:4d}  {k}")
        print("   e.g.:", repr((bad[0]["raw"] or "")[:200]), "| latency", bad[0]["latency_s"])

if sec("missing"):
    title("2. Partial models")
    for m in PARTIAL:
        miss = [i for i in IDS if i not in res[m]]
        print(f"{m}: {len(res[m])}/{N} rows saved, {len(miss)} missing; most affected sub-questions: {Counter(i.split('_')[0] for i in miss).most_common(5)}")

if sec("signif"):
    title("3. Paired significance (exact McNemar on per-row correctness)")
    print("NOTE: p-values are NOT corrected for the many comparisons made; only the largest gaps are safe from chance.\n")
    print(f"{'A':26s} {'B':26s} {'A only right':>12} {'B only right':>12} {'p':>8}")
    for a, b in [("glm-5.3", "glm-5.3-flash"), ("glm-5.3", "qwen3.5-9b-q8"), ("glm-5.3-flash", "qwen3.5-9b-q8"),
                 ("qwen3.5-9b-q8", "gemma4-e4b-q8"), ("qwen3.5-9b-q8", "qwen3.5-4b-q8"), ("qwen3.5-9b-q8", "gpt-oss-20b"),
                 ("gemma4-e4b-q8", "qwen3.5-4b-q8"), ("qwen3.5-4b-q8", "gpt-oss-20b"), ("qwen3.5-4b-q8", "phi4-14b-q4km"),
                 ("qwen3.5-4b-q8", "qwen3-8b-q8"), ("gpt-oss-20b", "phi4-14b-q4km"), ("qwen3-8b-q8", "phi4-mini-q8"),
                 ("qwen3.5-9b-q8", "phi4-mini-q8"), ("gpt-oss-20b", "nemotron-3.5-lightning-30b")]:
        if a in res and b in res and a in COMPLETE and b in COMPLETE:
            x, y, p = mcnemar(a, b)
            print(f"{a:26s} {b:26s} {x:12d} {y:12d} {p:8.4f} {'*' if p < 0.05 else ''}")
    if "nemotron-3-ultra-550b" in res:
        ids_u = [i for i in IDS if i in res["nemotron-3-ultra-550b"]]
        print(f"\nnemotron-ultra vs others on its {len(ids_u)} answered rows:")
        for b in ("glm-5.3", "qwen3.5-9b-q8", "gemma4-e4b-q8"):
            if b in COMPLETE:
                x, y, p = mcnemar("nemotron-3-ultra-550b", b, ids_u)
                print(f"   ultra vs {b:16s} ultra-only-right {x:3d}  other-only-right {y:3d}  p={p:.3f}")

if sec("conf"):
    title("4. Is the confidence useful? (AUROC of the relevance score; threshold sweep)")
    print(f"{'model':28s} {'AUROC':>6} {'best thr':>8} {'acc@best':>8} {'F1@best':>8} {'acc@0.6':>8}   most common confidences")
    for m in by_f1(COMPLETE):
        ids_v = [i for i in IDS if p_rel(m, i) is not None]
        a = auc([p_rel(m, i) for i in ids_v], [gold[i]["label"]["relevant"] for i in ids_v])
        f1_best, thr_best = max((metrics(model_pairs(m, thr=t / 100))["f1"], t / 100) for t in range(50, 100, 5))
        mb = metrics(model_pairs(m, thr=thr_best))
        confs = Counter(round(res[m][i]["verdict"]["confidence"], 2) for i in ids_v)
        print(f"{m:28s} {a:6.3f} {thr_best:8.2f} {mb['acc']:8.3f} {mb['f1']:8.3f} {metrics(model_pairs(m, thr=0.6))['acc']:8.3f}   "
              + ", ".join(f"{k}:{v}" for k, v in confs.most_common(3)))
    print("\n(AUROC 0.5 = confidence carries no information about relevance; 1.0 = perfect ranking. 'acc@0.6' is the production rule.)")

if sec("confsem"):
    title("4b. Do some models read 'confidence' as P(relevant) instead of 'how sure I am of my verdict'?")
    print("Share of 'not relevant' verdicts with confidence <= 0.3:")
    for m in sorted(COMPLETE):
        nots = [res[m][i]["verdict"] for i in res[m] if res[m][i]["verdict"] and not res[m][i]["verdict"]["relevant"]]
        low = [v for v in nots if v["confidence"] <= 0.3]
        print(f"  {m:28s} {len(low):3d} of {len(nots):3d} ({(len(low) / len(nots) if nots else 0):.0%})")
    print("\nAUROC when those low-confidence 'not relevant' verdicts are read as P(relevant):")
    for m in ("qwen3-8b-q8", "phi4-mini-q8", "qwen3.5-9b-q8"):
        if m in COMPLETE:
            ids = [i for i in IDS if p_rel(m, i) is not None]
            labs = [gold[i]["label"]["relevant"] for i in ids]
            print(f"  {m:20s} as defined {auc([p_rel(m, i) for i in ids], labs):.3f} -> re-read {auc([p_rel(m, i, True) for i in ids], labs):.3f}")

if sec("ensemble"):
    title("5. Combining models")
    local = ["qwen3.5-9b-q8", "gemma4-e4b-q8", "qwen3.5-4b-q8", "gpt-oss-20b", "phi4-14b-q4km"]

    def vote(models, k):
        return [(gold[i]["label"]["relevant"], sum(pred(m, i) for m in models) >= k) for i in IDS]

    def show(label, pairs):
        mt = metrics(pairs)
        print(f"{label:58s} acc {mt['acc']:.3f}  prec {mt['prec']:.3f}  rec {mt['rec']:.3f}  F1 {mt['f1']:.3f}  rejects-irrelevant {mt['spec']:.0%}")

    for m in ("qwen3.5-9b-q8", "gpt-oss-20b", "glm-5.3-flash"):
        show("single: " + m, model_pairs(m))
    show("qwen3.5-9b AND gpt-oss-20b (both must say relevant)", vote(["qwen3.5-9b-q8", "gpt-oss-20b"], 2))
    show("qwen3.5-9b AND gemma4 (both)", vote(["qwen3.5-9b-q8", "gemma4-e4b-q8"], 2))
    show("qwen3.5-4b AND gpt-oss-20b (both)", vote(["qwen3.5-4b-q8", "gpt-oss-20b"], 2))
    show("majority of 3: qwen3.5-9b, gemma4, gpt-oss", vote(["qwen3.5-9b-q8", "gemma4-e4b-q8", "gpt-oss-20b"], 2))
    show("majority of 3: qwen3.5-9b, qwen3.5-4b, gpt-oss", vote(["qwen3.5-9b-q8", "qwen3.5-4b-q8", "gpt-oss-20b"], 2))
    show("majority of the 5 local models", vote(local, 3))
    show("at least 4 of the 5 local models", vote(local, 4))
    show("majority of glm-5.3, glm-5.3-flash, qwen3.5-9b", vote(["glm-5.3", "glm-5.3-flash", "qwen3.5-9b-q8"], 2))

    pair_ok = {i: (pred("qwen3.5-9b-q8", i) and pred("gemma4-e4b-q8", i)) == gold[i]["label"]["relevant"] for i in IDS}
    print("\nIs 'qwen3.5-9b AND gemma4' better than a single model? (exact McNemar)")
    for other in ("qwen3.5-9b-q8", "gemma4-e4b-q8", "glm-5.3"):
        ok = {i: pred(other, i) == gold[i]["label"]["relevant"] for i in IDS}
        b01 = sum(1 for i in IDS if pair_ok[i] and not ok[i])
        b10 = sum(1 for i in IDS if ok[i] and not pair_ok[i])
        print(f"   vs {other:16s} pair-only-right {b01:3d}  other-only-right {b10:3d}  p={mcnemar_p(b01, b10):.3f}")

    print("\nAdding an embedding-similarity gate to a single model (threshold chosen by 5-fold cross-validation):")
    sims = {i: gold[i]["embedding_similarity"] for i in IDS}
    folds = [IDS[k::5] for k in range(5)]
    for m in ("qwen3.5-9b-q8", "qwen3.5-4b-q8", "gemma4-e4b-q8", "phi4-14b-q4km", "qwen3-8b-q8", "phi4-mini-q8", "gpt-oss-20b"):
        cv = []
        for k in range(5):
            train = [i for j in range(5) if j != k for i in folds[j]]
            best = max((metrics([(gold[i]["label"]["relevant"], pred(m, i) and sims[i] >= t / 100) for i in train])["acc"], t / 100)
                       for t in range(40, 85, 2))
            cv += [(gold[i]["label"]["relevant"], pred(m, i) and sims[i] >= best[1]) for i in folds[k]]
        a0, a1 = metrics(model_pairs(m))["acc"], metrics(cv)["acc"]
        print(f"   {m:22s} alone {a0:.3f} -> with similarity gate {a1:.3f}  ({a1 - a0:+.3f})")

if sec("cascade"):
    title("6. Cascade: embedding similarity decides the easy rows, the LLM only the middle band")
    for lo, hi in ((0.6, 0.8), (0.55, 0.85)):
        mid = [i for i in IDS if lo <= gold[i]["embedding_similarity"] < hi]
        print(f"\nband [{lo}, {hi}): the LLM runs on {len(mid)} of {N} rows ({1 - len(mid) / N:.0%} of LLM calls saved)")
        print(f"  {'model':28s} {'plain acc':>9} {'cascade acc':>11}")
        for m in sorted(COMPLETE, key=lambda m: -metrics(model_pairs(m))["acc"]):
            pairs = [(gold[i]["label"]["relevant"],
                      pred(m, i) if lo <= gold[i]["embedding_similarity"] < hi else gold[i]["embedding_similarity"] >= hi)
                     for i in IDS]
            print(f"  {m:28s} {metrics(model_pairs(m))['acc']:9.3f} {metrics(pairs)['acc']:11.3f}")

if sec("breakdown"):
    title("7. Where do models fail? (by label confidence, source, sub-question)")
    lowc = [i for i in IDS if gold[i]["label"]["confidence"] < 0.7]
    highc = [i for i in IDS if gold[i]["label"]["confidence"] >= 0.9]
    midc = [i for i in IDS if i not in lowc and i not in highc]
    print(f"label-confidence buckets: <0.7 -> {len(lowc)} rows | 0.7-0.9 -> {len(midc)} | >=0.9 -> {len(highc)}")
    print(f"{'model':28s} {'acc low-conf':>13} {'acc mid':>8} {'acc high-conf':>14} {'errors inside low-conf rows':>28}")
    for m in sorted(COMPLETE, key=lambda m: -metrics(model_pairs(m))["acc"]):
        errs = [i for i in IDS if pred(m, i) != gold[i]["label"]["relevant"]]
        print(f"{m:28s} {metrics(model_pairs(m, lowc))['acc']:13.3f} {metrics(model_pairs(m, midc))['acc']:8.3f} "
              f"{metrics(model_pairs(m, highc))['acc']:14.3f} {sum(i in lowc for i in errs):14d} of {len(errs):3d}")
    srcs = ["openalex", "arxiv", "both", "semantic_scholar"]
    print("\naccuracy by source:")
    print(f"{'model':28s}" + "".join(f"{s + ' (' + str(sum(gold[i]['source'] == s for i in IDS)) + ')':>24s}" for s in srcs))
    for m in ("glm-5.3", "qwen3.5-9b-q8", "qwen3.5-4b-q8", "gpt-oss-20b", "phi4-mini-q8"):
        print(f"{m:28s}" + "".join(f"{metrics(model_pairs(m, [i for i in IDS if gold[i]['source'] == s]))['acc']:24.3f}" for s in srcs))
    print("\nsub-questions with the lowest mean accuracy over the complete models:")
    per_q = defaultdict(list)
    qtext = {i.split("_")[0]: gold[i]["sub_question"] for i in IDS}
    for m in COMPLETE:
        for q in qtext:
            per_q[q].append(metrics(model_pairs(m, [i for i in IDS if i.startswith(q + "_")]))["acc"])
    for q, accs in sorted(per_q.items(), key=lambda kv: statistics.mean(kv[1]))[:8]:
        print(f"   {q}: mean acc {statistics.mean(accs):.2f} | {qtext[q][:80]}")

if sec("audit"):
    title("8. Label audit: rows where (almost) every model disagrees with the gold label")
    judges = [m for m in COMPLETE if m != "nemotron-3.5-lightning-30b"]       # its invalid replies would inflate the count
    ranked = sorted(((sum(pred(m, i) != gold[i]["label"]["relevant"] for m in judges), i) for i in IDS), reverse=True)
    print(f"{len(judges)} judges. Rows wrong for >= {len(judges) - 1}: {sum(1 for w, _ in ranked if w >= len(judges) - 1)} | "
          f">= 7: {sum(1 for w, _ in ranked if w >= 7)} | >= 5: {sum(1 for w, _ in ranked if w >= 5)}")
    print("how many judges are wrong -> number of rows:", sorted(Counter(w for w, _ in ranked).items()))
    for w, i in ranked[:14]:
        g = gold[i]
        v = res["glm-5.3"][i]["verdict"] if "glm-5.3" in res and i in res["glm-5.3"] else None
        print(f"\n[{i}] {w}/{len(judges)} judges disagree | gold={'REL' if g['label']['relevant'] else 'NOT'} (label conf {g['label']['confidence']}) "
              f"| sim {g['embedding_similarity']:.2f} | {g['source']}")
        print(f"   Q: {g['sub_question'][:100]}\n   T: {g['title'][:110]}\n   gold reason: {g['label']['reason']}")
        if v:
            print(f"   glm-5.3 says {'REL' if v['relevant'] else 'NOT'} ({v['confidence']}): {v['reason'][:140]}")

if sec("answered"):
    title("9. Accuracy on the replies a model actually answered (invalid / empty replies excluded)")
    for m in ("glm-5.3", "glm-5.3-flash", "nemotron-3.5-lightning-30b", "nemotron-3-ultra-550b"):
        if m not in res:
            continue
        ids = [i for i in res[m] if res[m][i]["verdict"] is not None]
        mt, allm = metrics(model_pairs(m, ids)), metrics(model_pairs(m))
        print(f"  {m:28s} answered {len(ids):3d}/{len(res[m])}: acc {mt['acc']:.3f} prec {mt['prec']:.3f} rec {mt['rec']:.3f} F1 {mt['f1']:.3f}"
              f"   (invalid counted as 'not relevant': acc {allm['acc']:.3f})")
    if "glm-5.3" in res:
        inv = [i for i in res["glm-5.3"] if res["glm-5.3"][i]["verdict"] is None]
        print(f"  glm-5.3 empty replies: {len(inv)}, of which {sum(gold[i]['label']['relevant'] for i in inv)} are relevant papers (counted as misses)")
    print("  (the answered subset can be easier than the whole set: a model that finishes quickly may be answering the simpler rows)")

if sec("clear"):
    title("10. Accuracy on the clearer rows only (label confidence >= 0.7)")
    clear = [i for i in IDS if gold[i]["label"]["confidence"] >= 0.7]
    print(f"{len(clear)} of {N} rows")
    for m in sorted(COMPLETE, key=lambda m: -metrics(model_pairs(m, clear))["acc"]):
        mt = metrics(model_pairs(m, clear))
        print(f"  {m:28s} acc {mt['acc']:.3f}  prec {mt['prec']:.3f}  rec {mt['rec']:.3f}  rejects-irrelevant {mt['spec']:.0%}")

if sec("latency"):
    title("11. Speed")
    print(f"{'model':28s} {'median s':>8} {'mean s':>7} {'p95 s':>7} {'max s':>7} {'median reply chars':>19}")
    for m in sorted(res, key=lambda m: statistics.median([r["latency_s"] for r in res[m].values()])):
        lat = sorted(r["latency_s"] for r in res[m].values())
        raws = [len(r["raw"] or "") for r in res[m].values()]
        print(f"{m:28s} {statistics.median(lat):8.2f} {statistics.mean(lat):7.2f} {lat[int(.95 * (len(lat) - 1))]:7.2f} {max(lat):7.1f} {statistics.median(raws):19.0f}")
