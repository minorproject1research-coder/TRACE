"""Turn the per-model result files into the tables of docs/MODEL_SELECTION_EVALUATION.md (printed and written to results/summary.md).

  venv/Scripts/python.exe evaluation/model_selection/summarize.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
sys.path.insert(0, str(HERE))
PROD_EMB = "bge-base-en-v1.5"
PROD_NLI = "DeBERTa-v3-large (TRACE)"


def load(kind):
    out = []
    for f in sorted((RES / kind).glob("*.json")):
        if f.name == "bm25.json":
            continue
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def paired_ci(a, b, reps=2000, seed=1, stat=lambda x: x.mean()):
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    n = len(a)
    d = [stat(a[i]) - stat(b[i]) for i in (rng.integers(0, n, n) for _ in range(reps))]
    return float(stat(a) - stat(b)), [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def published_scifact(repo_ids):
    """The SciFact nDCG@10 that the model card of each model reports (MTEB). Used to check that this harness gives about the same figures."""
    out = {}
    try:
        from huggingface_hub import ModelCard
        for rid in repo_ids:
            try:
                card = ModelCard.load(rid)
                for r in card.data.eval_results or []:
                    if "scifact" in (r.dataset_name or "").lower() and r.metric_type == "ndcg_at_10":
                        out[rid] = float(r.metric_value) / (100.0 if r.metric_value > 1 else 1.0)
                        break
            except Exception:
                pass
    except Exception:
        pass
    return out


def emb_tables():
    rows = load("embedding")
    bm = json.loads((RES / "embedding" / "bm25.json").read_text(encoding="utf-8")) if (RES / "embedding" / "bm25.json").exists() else {}
    L = []
    if not rows:
        return "(no embedding results yet)\n"
    prod = next((r for r in rows if r["name"] == PROD_EMB), None)
    pub = published_scifact(sorted({r["model_id"] for r in rows}))
    order = sorted(rows, key=lambda r: -r["t1"]["auc"])
    L += ["### Table E1: Stage 2 pre-filter, 360 labelled papers (T1)", "",
          "| Model | AUC (95% CI) | Average precision | Mean AUC inside a question | nDCG@5 | Irrelevant papers let through at 95% recall | Best-threshold accuracy |",
          "|---|---|---|---|---|---|---|"]
    for r in order:
        t = r["t1"]
        mark = " **(TRACE)**" if r["name"] == PROD_EMB else ""
        L.append(f"| {r['name']}{mark} | {t['auc']:.3f} ({t['auc_ci95'][0]:.3f} to {t['auc_ci95'][1]:.3f}) | {t['average_precision']:.3f} | {t['per_subquestion_auc']:.3f} | {t['ndcg5']:.3f} | "
                 f"{t['irrelevant_passing_at_95pct_recall'] * 100:.0f}% | {t['best_threshold']['accuracy']:.3f} |")
    if bm.get("t1"):
        L.append(f"| BM25 (words only, no model) | {bm['t1']['pooled_auc_rank_normalised']:.3f} (rank-normalised per question) | | {bm['t1']['per_subquestion_auc']:.3f} | | | |")
    L += [""]
    if prod:
        L += ["Paired difference of AUC against bge-base (same 360 rows, bootstrap 95% interval; an interval that contains 0 means no reliable difference):", ""]
        y = None
        for r in order:
            if r["name"] == PROD_EMB or "scores" not in r["t1"]:
                continue
            # labels are needed for AUC: rebuild from the dataset order
            if y is None:
                rows_ds = [json.loads(l) for l in (HERE.parents[0] / "relevance_judge" / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
                y = np.array([bool(x["label"]["relevant"]) for x in rows_ds])
            from eval_embeddings import auc
            sa, sb = np.array(r["t1"]["scores"]), np.array(prod["t1"]["scores"])
            rng = np.random.default_rng(3)
            diffs = []
            for _ in range(1000):
                i = rng.integers(0, len(y), len(y))
                diffs.append(auc(sa[i], y[i]) - auc(sb[i], y[i]))
            d = r["t1"]["auc"] - prod["t1"]["auc"]
            L.append(f"- {r['name']}: {d:+.3f} ({np.percentile(diffs, 2.5):+.3f} to {np.percentile(diffs, 97.5):+.3f})")
        L += [""]
    L += ["### Table E2: scientific claim to abstract retrieval, SciFact test (T2: 300 claims, 5,183 abstracts)", "",
          "| Model | nDCG@10 (95% CI) | Recall@10 | Recall@100 | MRR@10 | Published nDCG@10 (model card) |", "|---|---|---|---|---|---|"]
    for r in sorted([r for r in rows if "t2" in r], key=lambda r: -r["t2"]["ndcg10"]):
        t = r["t2"]
        mark = " **(TRACE)**" if r["name"] == PROD_EMB else ""
        p = pub.get(r["model_id"])
        L.append(f"| {r['name']}{mark} | {t['ndcg10']:.3f} ({t['ndcg10_ci95'][0]:.3f} to {t['ndcg10_ci95'][1]:.3f}) | {t['recall10']:.3f} | {t['recall100']:.3f} | {t['mrr10']:.3f} | "
                 f"{'%.3f' % p if p is not None and r['query_prefix'] == ('Represent this sentence for searching relevant passages: ' if 'bge' in r['name'] else r['query_prefix']) else ''} |")
    if bm.get("t2"):
        L.append(f"| BM25 (words only, no model) | {bm['t2']['ndcg10']:.3f} | | | | 0.665 (BEIR paper) |")
    L += [""]
    if prod and "t2" in prod:
        L += ["Paired difference of nDCG@10 against bge-base (same 300 claims):", ""]
        for r in sorted([r for r in rows if "t2" in r and r["name"] != PROD_EMB], key=lambda r: -r["t2"]["ndcg10"]):
            d, ci = paired_ci(r["t2"]["per_query_ndcg10"], prod["t2"]["per_query_ndcg10"])
            L.append(f"- {r['name']}: {d:+.3f} ({ci[0]:+.3f} to {ci[1]:+.3f})")
        L += [""]
    L += ["### Table E3: tasks on TRACE's own data (T3: 165 claims against 173 quotes of one run; 30 labelled claim pairs of Stage 4)", "",
          "| Model | Claim finds its own quote: top 1 | top 5 | MRR | Same-claim pairs: AUC |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["t3"]["mrr"]):
        t = r["t3"]
        mark = " **(TRACE)**" if r["name"] == PROD_EMB else ""
        L.append(f"| {r['name']}{mark} | {t['hit1']:.3f} | {t['hit5']:.3f} | {t['mrr']:.3f} | {t['merge_auc']:.3f} |")
    L += ["", "### Table E4: cost on this laptop (CPU only, Intel Core Ultra 7 155H, no GPU)", "",
          "| Model | Parameters (M) | Dimensions | Max tokens | Size on disk (MB) | Abstracts per second | Load time (s) |", "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["speed"]["parameters_million"]):
        s = r["speed"]
        mark = " **(TRACE)**" if r["name"] == PROD_EMB else ""
        L.append(f"| {r['name']}{mark} | {s['parameters_million']} | {s['dimensions']} | {s['max_seq_length']} | {s['size_on_disk_mb']} | {s['abstracts_per_second']} | {r['load_seconds']} |")
    return "\n".join(L) + "\n"


def nli_tables():
    rows = load("nli")
    if not rows:
        return "(no NLI results yet)\n"
    order = {n: i for i, n in enumerate([PROD_NLI, "DeBERTa-v3-base", "DeBERTa-v3-xsmall", "MiniLM2-L6-H768", "BART-large-mnli"])}
    rows.sort(key=lambda r: order.get(r["name"], 99))

    def g(r, t, k, fmt="{:.3f}"):
        v = (r["tasks"].get(t) or {}).get(k)
        return fmt.format(v) if v is not None else "n/a"
    L = ["### Table N1: scientific claims against evidence (human labels)", "",
         "SciFact rationales (N1a) have the same shape as the quote-to-claim pairs of TRACE. The thresholds are those of the code (support: entailment >= 0.50; conflict prefilter: contradiction >= 0.70).", "",
         "| Model | Support found (SUPPORT with entailment >= 0.50) | False support (CONTRADICT with entailment >= 0.50) | Conflict found (CONTRADICT with contradiction >= 0.70) | False conflict | AUC support vs contradict | 3-way accuracy on whole abstracts (N1b) | Macro-F1 (N1b) |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        mark = " **(TRACE)**" if r["name"] == PROD_NLI else ""
        L.append(f"| {r['name']}{mark} | {g(r, 'N1a_scifact_rationales', 'support_recall_at_050')} | {g(r, 'N1a_scifact_rationales', 'false_support_at_050')} | "
                 f"{g(r, 'N1a_scifact_rationales', 'conflict_recall_at_070')} | {g(r, 'N1a_scifact_rationales', 'false_conflict_at_070')} | {g(r, 'N1a_scifact_rationales', 'auc_support_vs_contradict')} | "
                 f"{g(r, 'N1b_scifact_abstracts', 'accuracy')} | {g(r, 'N1b_scifact_abstracts', 'macro_f1')} |")
    L += ["", "### Table N2: other public sets", "",
          "| Model | SciTail accuracy (entailment vs not, argmax) | SciTail F1 of entailment at 0.50 | SciTail AUC | MNLI matched accuracy (1,000) |", "|---|---|---|---|---|"]
    for r in rows:
        mark = " **(TRACE)**" if r["name"] == PROD_NLI else ""
        L.append(f"| {r['name']}{mark} | {g(r, 'N2_scitail', 'accuracy_argmax')} | {g(r, 'N2_scitail', 'f1_at_050')} | {g(r, 'N2_scitail', 'auc')} | {g(r, 'N3_mnli', 'accuracy')} |")
    L += ["", "### Table N3: TRACE's own labelled pairs (small; labels by an LLM annotator)", "",
          "| Model | Support set (16 pairs): precision / recall at 0.50 | Conflict set (41 pairs, 9 conflicts): conflicts found at 0.70 | Flagged | False alarms |", "|---|---|---|---|---|"]
    for r in rows:
        mark = " **(TRACE)**" if r["name"] == PROD_NLI else ""
        L.append(f"| {r['name']}{mark} | {g(r, 'N4a_trace_support', 'precision_at_050')} / {g(r, 'N4a_trace_support', 'recall_at_050')} | {g(r, 'N4b_trace_conflict', 'recall_at_070')} | "
                 f"{g(r, 'N4b_trace_conflict', 'flagged_at_070', '{}')} | {g(r, 'N4b_trace_conflict', 'false_alarms_at_070', '{}')} |")
    L += ["", "### Table N4: agreement with the TRACE model on the real quote-to-claim pairs of run 9b56d11b (no gold labels)", "",
          "| Model | Pairs | Same 3-way label as the large model | Same support decision (entailment >= 0.50) | Supports the large model finds that this model loses | Supports this model adds |", "|---|---|---|---|---|---|"]
    for r in rows:
        t = r["tasks"].get("N5_trace_real_pairs")
        if t:
            L.append(f"| {r['name']} | {t['n']} | {t['same_label_as_large']:.3f} | {t['same_support_decision_as_large']:.3f} | {t['supports_lost_vs_large']} of {t['large_accepts']} | {t['supports_added_vs_large']} |")
    L += ["", "### Table N5: cost on this laptop (CPU only)", "",
          "| Model | Parameters (M) | Short pairs per second (SciTail) | Long pairs per second (whole abstracts) | Load time (s) |", "|---|---|---|---|---|"]
    for r in rows:
        mark = " **(TRACE)**" if r["name"] == PROD_NLI else ""
        pps = r.get("pairs_per_second", {})
        L.append(f"| {r['name']}{mark} | {r.get('parameters_million', 'n/a')} | {pps.get('N2_scitail', 'n/a')} | {pps.get('N1b_scifact_abstracts', 'n/a')} | {r.get('load_seconds', 'n/a')} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    text = "## Embedding models\n\n" + emb_tables() + "\n## NLI models\n\n" + nli_tables()
    (RES / "summary.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))
