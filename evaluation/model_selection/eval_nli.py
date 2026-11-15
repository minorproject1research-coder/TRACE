"""Why DeBERTa-v3-large for entailment? Compare the NLI model of TRACE (Stages 4 and 5) with smaller models and one other large model. CPU only, no Groq.

  venv/Scripts/python.exe evaluation/model_selection/eval_nli.py [--models name,name] [--out evaluation/model_selection/results]

TRACE uses NLI in three ways (thresholds as in the code): support = P(entailment | quote -> claim) >= 0.50 (Stage 4 fact_checker, Stage 5 grounding);
conflict prefilter = P(contradiction | their quote -> our claim) >= 0.70 (Stage 4 contradiction_detector; a judge decides afterwards, so recall matters most).
Tasks (gold labels, none of them written by the model under test):
  N1a SciFact rationales: the evidence sentences of an abstract against a claim; gold SUPPORT or CONTRADICT (human labels, 773 pairs). Same shape as quote -> claim.
  N1b SciFact abstracts: the whole abstract against the claim, gold SUPPORT / CONTRADICT / NOT ENOUGH INFO (450 pairs, 150 each, seed 42).
  N2  SciTail test (science questions, 2,126 pairs): entailment or not.
  N3  MNLI validation matched (1,000 pairs, seed 42): general 3-class sanity check (all models saw MNLI training data).
  N4  TRACE labelled sets of Stage 4 (reports/stage4_eval_set.json: 16 support pairs, 41 conflict pairs; labels by an LLM annotator, small).
  N5  Agreement with the production model on the real quote -> claim pairs of run 9b56d11b (no gold labels: only "does it decide as the large model does").
Per-pair probabilities are saved per model (resumable): results/nli/<name>.json. Summarised by summarize_nli.py.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.stats import rankdata

# float32 for every model: the DeBERTa models are stored in float16 and transformers 5 would run them in half precision on the CPU (about 19x slower, see the doc).
ROOT = Path(__file__).resolve().parents[2]
MODELS = [
    ("DeBERTa-v3-large (TRACE)", "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"),
    ("DeBERTa-v3-base", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"),
    ("DeBERTa-v3-xsmall", "cross-encoder/nli-deberta-v3-xsmall"),
    ("MiniLM2-L6-H768", "cross-encoder/nli-MiniLM2-L6-H768"),
    ("BART-large-mnli", "facebook/bart-large-mnli"),
]
CLASSES = ["entailment", "neutral", "contradiction"]
ENTAIL_MIN, CONTRA_MIN = 0.50, 0.70


def clean_text(t):
    import unicodedata
    t = unicodedata.normalize("NFKC", t or "").replace("‐", "-").replace("‑", "-").replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- data
def hf(repo, f, kind="dataset"):
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo, f, repo_type=kind)


def build_tasks():
    import pandas as pd
    rng = np.random.default_rng(42)
    tasks = {}
    sf = pd.concat([pd.read_parquet(hf("tasksource/scifact_entailment", f"default/{s}.parquet")) for s in ("train", "validation")], ignore_index=True)
    gold_map = {"SUPPORT": "entailment", "NEI": "neutral", "CONTRADICT": "contradiction"}
    a_rows, b_rows = [], []
    for _, r in sf.iterrows():
        sents = list(r["abstract"])
        ev = [int(i) for i in r["evidence"]]
        if r["verdict"] in ("SUPPORT", "CONTRADICT") and ev:
            a_rows.append((" ".join(sents[i] for i in ev if i < len(sents)), r["claim"], gold_map[r["verdict"]]))
        b_rows.append((" ".join(sents), r["claim"], gold_map[r["verdict"]]))
    tasks["N1a_scifact_rationales"] = a_rows
    pick = []
    for g in ("entailment", "neutral", "contradiction"):
        idx = [i for i, x in enumerate(b_rows) if x[2] == g]
        pick += list(rng.choice(idx, 150, replace=False))
    tasks["N1b_scifact_abstracts"] = [b_rows[i] for i in sorted(pick)]
    st = pd.read_parquet(hf("allenai/scitail", "dgem_format/test-00000-of-00001.parquet"))
    tasks["N2_scitail"] = [(r["premise"], r["hypothesis"], "entailment" if r["label"] == "entails" else "neutral") for _, r in st.iterrows()]
    mn = pd.read_parquet(hf("nyu-mll/multi_nli", "data/validation_matched-00000-of-00001.parquet"))
    ids = rng.choice(len(mn), 1000, replace=False)
    names = {0: "entailment", 1: "neutral", 2: "contradiction"}
    tasks["N3_mnli"] = [(mn.iloc[i]["premise"], mn.iloc[i]["hypothesis"], names[int(mn.iloc[i]["label"])]) for i in ids]
    ev = json.loads((ROOT / "reports/stage4_eval_set.json").read_text(encoding="utf-8"))
    tasks["N4a_trace_support"] = [(x["quote"], x["claim"], "entailment" if x["supports"] else "not_entailment") for x in ev["support"]]
    tasks["N4b_trace_conflict"] = [(x["quote_b"], x["a"], "contradiction" if x["conflicts"] else "not_contradiction") for x in ev["conflict"]]
    rep = json.loads((ROOT / "reports/ppt_example/evidence_report.json").read_text(encoding="utf-8"))
    n5 = []
    for sq in rep["subQuestions"]:
        for c in (sq.get("factCheck") or {}).get("claims") or []:
            for e in c.get("evidence", []):
                if e.get("relation") in ("supports", "near_match") and e.get("quote"):
                    n5.append((e["quote"], c["claim"], "unlabelled"))
    tasks["N5_trace_real_pairs"] = n5
    return tasks


# ---------------------------------------------------------------- model
def load(model_id):
    from sentence_transformers import CrossEncoder
    m = CrossEncoder(model_id, device="cpu", model_kwargs={"torch_dtype": torch.float32})
    cfg = getattr(m, "config", None) or m.model.config
    idx = {str(l).lower(): int(i) for i, l in cfg.id2label.items()}
    assert {"contradiction", "entailment", "neutral"} <= set(idx), cfg.id2label
    return m, idx


def probs(m, idx, pairs, batch=16):
    out = np.asarray(m.predict([(clean_text(p), clean_text(h)) for p, h, _ in pairs], batch_size=batch, show_progress_bar=False), dtype=float)
    if not (np.all((out >= 0) & (out <= 1)) and np.allclose(out.sum(axis=1), 1.0, atol=1e-3)):
        z = out - out.max(axis=1, keepdims=True)
        out = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
    return np.stack([out[:, idx[c]] for c in CLASSES], axis=1)          # columns: entailment, neutral, contradiction


# ---------------------------------------------------------------- metrics
def auc(scores, labels):
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def macro_f1(gold, pred, classes):
    f = []
    for c in classes:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        f.append(2 * tp / max(1, 2 * tp + fp + fn))
    return float(np.mean(f))


def score(task, P, pairs):
    gold = [g for _, _, g in pairs]
    y = np.array(gold)
    pred = np.array([CLASSES[i] for i in P.argmax(1)])
    ent, con = P[:, 0], P[:, 2]
    r = {"n": len(pairs)}
    if task == "N1a_scifact_rationales":
        S, C = y == "entailment", y == "contradiction"
        r.update(support_recall_at_050=float((ent[S] >= ENTAIL_MIN).mean()), false_support_at_050=float((ent[C] >= ENTAIL_MIN).mean()),
                 conflict_recall_at_070=float((con[C] >= CONTRA_MIN).mean()), false_conflict_at_070=float((con[S] >= CONTRA_MIN).mean()),
                 auc_support_vs_contradict=auc((ent - con)[S | C], S[S | C]), n_support=int(S.sum()), n_contradict=int(C.sum()),
                 accuracy_two_way=float(np.mean(np.where(ent >= con, "entailment", "contradiction")[S | C] == y[S | C])))
    elif task in ("N1b_scifact_abstracts", "N3_mnli"):
        r.update(accuracy=float((pred == y).mean()), macro_f1=macro_f1(gold, list(pred), CLASSES),
                 confusion={g: {c: int(((y == g) & (pred == c)).sum()) for c in CLASSES} for g in CLASSES})
        if task == "N1b_scifact_abstracts":
            S, C = y == "entailment", y == "contradiction"
            r.update(support_recall_at_050=float((ent[S] >= ENTAIL_MIN).mean()), false_support_at_050=float((ent[~S] >= ENTAIL_MIN).mean()),
                     conflict_recall_at_070=float((con[C] >= CONTRA_MIN).mean()), auc_support=auc(ent, S))
    elif task == "N2_scitail":
        S = y == "entailment"
        p_ent = ent >= ENTAIL_MIN
        tp, fp, fn = (p_ent & S).sum(), (p_ent & ~S).sum(), (~p_ent & S).sum()
        r.update(accuracy_argmax=float(((pred == "entailment") == S).mean()), accuracy_at_050=float((p_ent == S).mean()), precision_at_050=float(tp / max(1, tp + fp)),
                 recall_at_050=float(tp / max(1, tp + fn)), f1_at_050=float(2 * tp / max(1, 2 * tp + fp + fn)), auc=auc(ent, S))
    elif task == "N4a_trace_support":
        S = y == "entailment"
        p = ent >= ENTAIL_MIN
        r.update(precision_at_050=float((p & S).sum() / max(1, p.sum())), recall_at_050=float((p & S).sum() / max(1, S.sum())), auc=auc(ent, S), n_positive=int(S.sum()))
    elif task == "N4b_trace_conflict":
        C = y == "contradiction"
        p = con >= CONTRA_MIN
        r.update(recall_at_070=float((p & C).sum() / max(1, C.sum())), flagged_at_070=int(p.sum()), false_alarms_at_070=int((p & ~C).sum()), auc=auc(con, C), n_positive=int(C.sum()))
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="")
    ap.add_argument("--out", default="evaluation/model_selection/results")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args(argv)
    out = ROOT / args.out / "nli"
    out.mkdir(parents=True, exist_ok=True)
    tasks = build_tasks()
    print({k: len(v) for k, v in tasks.items()}, flush=True)
    want = {m.strip() for m in args.models.split(",") if m.strip()}
    for name, mid in MODELS:
        if want and name not in want:
            continue
        f = out / (re.sub(r"[^A-Za-z0-9.+-]+", "_", name) + ".json")
        res = json.loads(f.read_text(encoding="utf-8")) if f.exists() and not args.redo else {"name": name, "model_id": mid, "tasks": {}, "probs": {}}
        if all(t in res["tasks"] or t == "N5_trace_real_pairs" for t in tasks) and "N5_trace_real_pairs" in res["probs"]:
            print("skip (done)", name, flush=True)
            continue
        print("==", name, flush=True)
        t0 = time.time()
        try:
            m, idx = load(mid)
        except Exception as e:
            print("  cannot load:", repr(e)[:200], flush=True)
            continue
        res["load_seconds"] = round(time.time() - t0, 1)
        res["parameters_million"] = round(sum(p.numel() for p in m.model.parameters()) / 1e6, 1)
        res["label_order"] = {str(k): v for k, v in (getattr(m, "config", None) or m.model.config).id2label.items()}
        for task, pairs in tasks.items():
            if task in res["probs"]:
                continue
            t1 = time.time()
            P = probs(m, idx, pairs)
            dt = time.time() - t1
            res["probs"][task] = np.round(P, 4).tolist()
            res.setdefault("seconds", {})[task] = round(dt, 1)
            res.setdefault("pairs_per_second", {})[task] = round(len(pairs) / dt, 2)
            if task != "N5_trace_real_pairs":
                res["tasks"][task] = score(task, P, pairs)
            print(f"  {task}: {len(pairs)} pairs in {dt:.0f} s  {json.dumps({k: round(v, 3) for k, v in (res['tasks'].get(task) or {}).items() if isinstance(v, float)})}", flush=True)
            f.write_text(json.dumps(res), encoding="utf-8")
        del m
    # N5: agreement with the production model
    ref = out / "DeBERTa-v3-large_TRACE_.json"
    if ref.exists():
        R = json.loads(ref.read_text(encoding="utf-8"))
        if "N5_trace_real_pairs" in R["probs"]:
            Rp = np.array(R["probs"]["N5_trace_real_pairs"])
            for fl in out.glob("*.json"):
                r = json.loads(fl.read_text(encoding="utf-8"))
                if "N5_trace_real_pairs" not in r.get("probs", {}):
                    continue
                P = np.array(r["probs"]["N5_trace_real_pairs"])
                same_arg = float((P.argmax(1) == Rp.argmax(1)).mean())
                same_sup = float(((P[:, 0] >= ENTAIL_MIN) == (Rp[:, 0] >= ENTAIL_MIN)).mean())
                lost = int(((Rp[:, 0] >= ENTAIL_MIN) & (P[:, 0] < ENTAIL_MIN)).sum())
                gained = int(((Rp[:, 0] < ENTAIL_MIN) & (P[:, 0] >= ENTAIL_MIN)).sum())
                r["tasks"]["N5_trace_real_pairs"] = {"n": len(P), "same_label_as_large": same_arg, "same_support_decision_as_large": same_sup,
                                                     "large_accepts": int((Rp[:, 0] >= ENTAIL_MIN).sum()), "supports_lost_vs_large": lost, "supports_added_vs_large": gained}
                fl.write_text(json.dumps(r), encoding="utf-8")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
