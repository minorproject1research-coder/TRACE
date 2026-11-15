"""Why bge-base-en-v1.5? Compare the embedding model of TRACE with other models on the tasks it does in the pipeline. CPU only, no Groq.

  venv/Scripts/python.exe evaluation/model_selection/eval_embeddings.py [--models name,name] [--skip-scifact] [--out evaluation/model_selection/results]

Tasks (all models see the same data; each model is used the way TRACE calls it: no instruction, cosine of normalised vectors):
  T1  Stage 2 pre-filter: sub-question vs abstract, 360 labelled papers (evaluation/relevance_judge/dataset.jsonl; labels by one LLM annotator).
  T2  Scientific claim -> abstract retrieval (SciFact, BEIR test split: 300 claims, 5,183 abstracts). Public, human-labelled, the nearest public
      task to "find the passage that backs this claim" (Stages 3 and 4).
  T3  Claim -> its own quote among all quotes of one real run (run 9b56d11b, 165 claims) and the 30 hand-labelled "same claim" pairs of Stage 4.
  T4  Speed on this CPU (no GPU): load time, abstracts per second, size, dimensions.
Results are saved per model (resumable): results/embedding/<name>.json. Numbers are summarised by summarize_embeddings.py.
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from scipy.stats import rankdata

# Weights are loaded in float32 for every model: transformers 5 keeps the stored precision, and gte-base is stored in float16, which the CPU runs about 4x slower.
ROOT = Path(__file__).resolve().parents[2]
BGE_INSTR = "Represent this sentence for searching relevant passages: "
# name, Hugging Face id, query prefix, document prefix
MODELS = [
    ("all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2", "", ""),
    ("bge-small-en-v1.5", "BAAI/bge-small-en-v1.5", "", ""),
    ("bge-base-en-v1.5", "BAAI/bge-base-en-v1.5", "", ""),                                   # the model of TRACE
    ("bge-base-en-v1.5 + query instruction", "BAAI/bge-base-en-v1.5", BGE_INSTR, ""),         # same model, the retrieval prompt of its model card
    ("bge-large-en-v1.5", "BAAI/bge-large-en-v1.5", "", ""),
    ("e5-base-v2", "intfloat/e5-base-v2", "query: ", "passage: "),
    ("e5-large-v2", "intfloat/e5-large-v2", "query: ", "passage: "),
    ("all-mpnet-base-v2", "sentence-transformers/all-mpnet-base-v2", "", ""),
    ("gte-base", "thenlper/gte-base", "", ""),
]


# ---------------------------------------------------------------- metrics
def auc(scores, labels):
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def average_precision(scores, labels):
    order = np.argsort(-np.asarray(scores, float), kind="stable")
    y = np.asarray(labels, bool)[order]
    hits = np.cumsum(y)
    return float((hits[y] / (np.nonzero(y)[0] + 1)).mean()) if y.any() else float("nan")


def fpr_at_tpr(scores, labels, tpr):
    """Share of irrelevant papers that pass when the threshold keeps `tpr` of the relevant ones."""
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    pos = np.sort(s[y])[::-1]
    k = int(np.ceil(tpr * len(pos))) - 1
    thr = pos[k]
    return float((s[~y] >= thr).mean()), float(thr)


def best_threshold(scores, labels):
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    best = (-1.0, None, None)
    for t in np.unique(s):
        p = s >= t
        tp, fp, fn = (p & y).sum(), (p & ~y).sum(), (~p & y).sum()
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        acc = (p == y).mean()
        if acc > best[0]:
            best = (float(acc), float(t), float(f1))
    return {"accuracy": best[0], "threshold": best[1], "f1": best[2]}


def ndcg_at(ranked_rel, k, n_rel_total):
    gains = np.asarray(ranked_rel[:k], float)
    dcg = (gains / np.log2(np.arange(2, len(gains) + 2))).sum()
    ideal = (1.0 / np.log2(np.arange(2, min(n_rel_total, k) + 2))).sum()
    return float(dcg / ideal) if ideal > 0 else 0.0


def bootstrap_ci(values_fn, n, reps=1000, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        v = values_fn(idx)
        if not np.isnan(v):
            out.append(v)
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


# ---------------------------------------------------------------- data
def load_t1():
    rows = [json.loads(l) for l in (ROOT / "evaluation/relevance_judge/dataset.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return [{"sq": r["sub_question_id"], "q": r["sub_question"], "d": r["abstract"] or r["title"],
             "y": bool(r["label"]["relevant"]), "bge_sim": r.get("embedding_similarity")} for r in rows]


def load_scifact():
    from huggingface_hub import hf_hub_download
    corpus, queries, qrels = {}, {}, defaultdict(dict)
    for l in open(hf_hub_download("mteb/scifact", "corpus.jsonl", repo_type="dataset"), encoding="utf-8"):
        d = json.loads(l)
        corpus[str(d["_id"])] = ((d.get("title") or "") + " " + (d.get("text") or "")).strip()
    for l in open(hf_hub_download("mteb/scifact", "queries.jsonl", repo_type="dataset"), encoding="utf-8"):
        d = json.loads(l)
        queries[str(d["_id"])] = d["text"]
    for i, l in enumerate(open(hf_hub_download("mteb/scifact", "qrels/test.tsv", repo_type="dataset"), encoding="utf-8")):
        if i == 0 and l.lower().startswith("query"):
            continue
        q, d, s = l.rstrip("\n").split("\t")
        if int(s) > 0:
            qrels[q][d] = int(s)
    qids = [q for q in qrels if q in queries]
    return corpus, queries, {q: qrels[q] for q in qids}


def load_t3():
    ev = json.loads((ROOT / "reports/ppt_example/evidence_report.json").read_text(encoding="utf-8"))
    quotes, claims = [], []
    qidx = {}
    for sq in ev["subQuestions"]:
        for c in (sq.get("factCheck") or {}).get("claims") or []:
            gold = []
            for e in c.get("evidence", []):
                if e.get("relation") != "supports" or not e.get("quote"):
                    continue
                key = (e["sourceId"], e["quote"].strip())
                if key not in qidx:
                    qidx[key] = len(quotes)
                    quotes.append(e["quote"].strip())
                gold.append(qidx[key])
            if gold:
                claims.append({"claim": c["claim"], "gold": sorted(set(gold))})
    pairs = json.loads((ROOT / "reports/stage4_eval_set.json").read_text(encoding="utf-8"))["merge"]
    return quotes, claims, pairs


def bm25_scores(queries, docs, k1=1.5, b=0.75):
    tok = lambda t: re.findall(r"[a-z0-9]+", t.lower())              # noqa: E731
    D = [tok(d) for d in docs]
    N = len(D)
    avg = np.mean([len(d) for d in D])
    df = defaultdict(int)
    for d in D:
        for w in set(d):
            df[w] += 1
    idf = {w: np.log(1 + (N - n + 0.5) / (n + 0.5)) for w, n in df.items()}
    tfs = [defaultdict(int) for _ in D]
    postings = defaultdict(list)
    for i, d in enumerate(D):
        for w in d:
            tfs[i][w] += 1
        for w in tfs[i]:
            postings[w].append(i)
    lens = np.array([len(d) for d in D])
    out = np.zeros((len(queries), N))
    for qi, q in enumerate(queries):
        for w in set(tok(q)):
            if w not in idf:
                continue
            for i in postings[w]:
                f = tfs[i][w]
                out[qi, i] += idf[w] * f * (k1 + 1) / (f + k1 * (1 - b + b * lens[i] / avg))
    return out


# ---------------------------------------------------------------- tasks
def encode(model, texts, prefix, batch=32):
    return np.asarray(model.encode([prefix + t for t in texts], batch_size=batch, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


def task_t1(model, qp, dp, rows):
    t0 = time.time()
    qs = sorted({r["q"] for r in rows})
    qv = dict(zip(qs, encode(model, qs, qp)))
    dv = encode(model, [r["d"] for r in rows], dp)
    sims = np.array([float(dv[i] @ qv[r["q"]]) for i, r in enumerate(rows)])
    y = np.array([r["y"] for r in rows])
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[r["sq"]].append(i)
    sq_auc, sq_ndcg5 = [], []
    for ids in by.values():
        a = auc(sims[ids], y[ids])
        if not np.isnan(a):
            sq_auc.append(a)
        order = np.argsort(-sims[ids])
        sq_ndcg5.append(ndcg_at(y[ids][order], 5, int(y[ids].sum())))
    f95, t95 = fpr_at_tpr(sims, y, 0.95)
    f90, t90 = fpr_at_tpr(sims, y, 0.90)
    a = auc(sims, y)
    return {"n": len(rows), "relevant": int(y.sum()), "auc": a, "auc_ci95": bootstrap_ci(lambda idx: auc(sims[idx], y[idx]), len(rows)),
            "average_precision": average_precision(sims, y), "per_subquestion_auc": float(np.mean(sq_auc)), "ndcg5": float(np.mean(sq_ndcg5)),
            "irrelevant_passing_at_95pct_recall": f95, "threshold_at_95pct_recall": t95, "irrelevant_passing_at_90pct_recall": f90, "threshold_at_90pct_recall": t90,
            "best_threshold": best_threshold(sims, y), "seconds": round(time.time() - t0, 1), "scores": [round(float(s), 5) for s in sims]}


def task_t2(model, qp, dp, corpus, queries, qrels, cache):
    t0 = time.time()
    ids = list(corpus)
    if "doc" not in cache or cache["dp"] != dp:
        cache["doc"], cache["dp"] = encode(model, [corpus[i] for i in ids], dp, batch=16), dp
    qids = list(qrels)
    qv = encode(model, [queries[q] for q in qids], qp)
    S = qv @ cache["doc"].T
    nd10, rc10, rc100, mrr = [], [], [], []
    for k, q in enumerate(qids):
        order = np.argsort(-S[k])[:100]
        rel = qrels[q]
        ranked = [1 if ids[j] in rel else 0 for j in order]
        nd10.append(ndcg_at(ranked, 10, len(rel)))
        rc10.append(sum(ranked[:10]) / len(rel))
        rc100.append(sum(ranked) / len(rel))
        first = next((i for i, v in enumerate(ranked) if v), None)
        mrr.append(1 / (first + 1) if first is not None and first < 10 else 0.0)
    nd = np.array(nd10)
    return {"queries": len(qids), "documents": len(ids), "ndcg10": float(nd.mean()), "ndcg10_ci95": bootstrap_ci(lambda idx: float(nd[idx].mean()), len(nd)),
            "recall10": float(np.mean(rc10)), "recall100": float(np.mean(rc100)), "mrr10": float(np.mean(mrr)), "seconds": round(time.time() - t0, 1),
            "per_query_ndcg10": [round(float(x), 4) for x in nd]}


def task_t3(model, qp, dp, quotes, claims, pairs):
    qv = encode(model, [c["claim"] for c in claims], qp)
    dv = encode(model, quotes, dp)
    S = qv @ dv.T
    h1 = h5 = 0
    rr = []
    for k, c in enumerate(claims):
        order = list(np.argsort(-S[k]))
        pos = min(order.index(g) for g in c["gold"]) + 1
        h1 += pos == 1
        h5 += pos <= 5
        rr.append(1 / pos)
    a = encode(model, [p["a"] for p in pairs], qp)
    b = encode(model, [p["b"] for p in pairs], qp)
    sim = (a * b).sum(1)
    y = np.array([bool(p["same"]) for p in pairs])
    return {"claims": len(claims), "quotes": len(quotes), "hit1": h1 / len(claims), "hit5": h5 / len(claims), "mrr": float(np.mean(rr)),
            "merge_pairs": len(pairs), "merge_same": int(y.sum()), "merge_auc": auc(sim, y)}


def task_speed(model, rows, repo_id):
    texts = [r["d"] for r in rows[:96]]
    model.encode(texts[:8], batch_size=8, show_progress_bar=False)               # warm-up
    t0 = time.time()
    model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
    dt = time.time() - t0
    q = ["How effective is federated learning compared with centralized training for medical image analysis?"] * 16
    t0 = time.time()
    model.encode(q, batch_size=16, show_progress_bar=False)
    dq = time.time() - t0
    size = 0
    try:
        from huggingface_hub import scan_cache_dir
        for repo in scan_cache_dir().repos:
            if repo.repo_id == repo_id:
                size = repo.size_on_disk
    except Exception:
        pass
    params = sum(p.numel() for p in model[0].auto_model.parameters())
    return {"abstracts_per_second": round(len(texts) / dt, 2), "seconds_for_96_abstracts": round(dt, 1), "short_queries_per_second": round(len(q) / dq, 1),
            "parameters_million": round(params / 1e6, 1), "dimensions": int(model.get_sentence_embedding_dimension()), "max_seq_length": int(model.max_seq_length),
            "size_on_disk_mb": round(size / 1e6)}


def lexical_baseline(t1, scifact, out):
    """BM25 (words only, no model) as the floor: what do embeddings add?"""
    res = {}
    uq = sorted({r["q"] for r in t1})
    ud = sorted({r["d"] for r in t1})
    S = bm25_scores(uq, ud)
    qi = {q: i for i, q in enumerate(uq)}
    di = {d: i for i, d in enumerate(ud)}
    sims = np.array([S[qi[r["q"]], di[r["d"]]] for r in t1])
    y = np.array([r["y"] for r in t1])
    by = defaultdict(list)
    for i, r in enumerate(t1):
        by[r["sq"]].append(i)
    z = np.zeros(len(t1))
    for ids in by.values():                                      # BM25 scales differ between questions: rank-normalise inside each question
        z[ids] = (rankdata(sims[ids]) - 1) / max(1, len(ids) - 1)
    res["t1"] = {"per_subquestion_auc": float(np.mean([auc(sims[i], y[i]) for i in by.values() if y[i].any() and (~y[i]).any()])), "pooled_auc_rank_normalised": auc(z, y)}
    if scifact:
        corpus, queries, qrels = scifact
        ids = list(corpus)
        qids = list(qrels)
        B = bm25_scores([queries[q] for q in qids], [corpus[i] for i in ids])
        nd = []
        for k, q in enumerate(qids):
            order = np.argsort(-B[k])[:10]
            nd.append(ndcg_at([1 if ids[j] in qrels[q] else 0 for j in order], 10, len(qrels[q])))
        res["t2"] = {"ndcg10": float(np.mean(nd))}
    (out / "bm25.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="")
    ap.add_argument("--skip-scifact", action="store_true")
    ap.add_argument("--out", default="evaluation/model_selection/results")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--speed-only", action="store_true", help="only re-measure the speed of models that already have a result file (run it on an idle machine)")
    args = ap.parse_args(argv)
    out = ROOT / args.out / "embedding"
    if args.speed_only:
        from sentence_transformers import SentenceTransformer
        t1 = load_t1()
        want = {m.strip() for m in args.models.split(",") if m.strip()}
        for name, mid, qp, dp in MODELS:
            f = out / (re.sub(r"[^A-Za-z0-9.+-]+", "_", name) + ".json")
            if not f.exists() or (want and name not in want):
                continue
            res = json.loads(f.read_text(encoding="utf-8"))
            t0 = time.time()
            model = SentenceTransformer(mid, device="cpu", model_kwargs={"torch_dtype": torch.float32})
            res["load_seconds"] = round(time.time() - t0, 1)
            res["speed"] = task_speed(model, t1, mid)
            res["speed"]["measured_again_on_idle_machine"] = True
            f.write_text(json.dumps(res, indent=1), encoding="utf-8")
            print(name, res["speed"]["abstracts_per_second"], "abstracts/s", flush=True)
            del model
        return 0
    out.mkdir(parents=True, exist_ok=True)
    from sentence_transformers import SentenceTransformer
    t1 = load_t1()
    scifact = None if args.skip_scifact else load_scifact()
    quotes, claims, pairs = load_t3()
    print(f"T1 {len(t1)} rows; T2 {'skipped' if scifact is None else str(len(scifact[0])) + ' docs, ' + str(len(scifact[2])) + ' queries'}; "
          f"T3 {len(claims)} claims, {len(quotes)} quotes, {len(pairs)} merge pairs", flush=True)
    if not (out / "bm25.json").exists() or args.redo:
        print("BM25 baseline", lexical_baseline(t1, scifact, out), flush=True)
    want = {m.strip() for m in args.models.split(",") if m.strip()}
    todo = [m for m in MODELS if not want or m[0] in want]
    cache_by_id = {}
    for k, (name, mid, qp, dp) in enumerate(todo):
        f = out / (re.sub(r"[^A-Za-z0-9.+-]+", "_", name) + ".json")
        if f.exists() and not args.redo:
            print("skip (done)", name, flush=True)
            continue
        print("==", name, flush=True)
        t0 = time.time()
        try:
            model = SentenceTransformer(mid, device="cpu", model_kwargs={"torch_dtype": torch.float32})
        except Exception as e:                                       # not downloaded: say so and go on
            print("  cannot load:", repr(e)[:200], flush=True)
            continue
        load_s = round(time.time() - t0, 1)
        res = {"name": name, "model_id": mid, "query_prefix": qp, "doc_prefix": dp, "load_seconds": load_s}
        res["speed"] = task_speed(model, t1, mid)
        print(f"  speed {res['speed']['abstracts_per_second']} abstracts/s", flush=True)
        res["t1"] = task_t1(model, qp, dp, t1)
        print(f"  T1 auc {res['t1']['auc']:.3f}  per-sq auc {res['t1']['per_subquestion_auc']:.3f}  ({res['t1']['seconds']} s)", flush=True)
        res["t3"] = task_t3(model, qp, dp, quotes, claims, pairs)
        print(f"  T3 hit@1 {res['t3']['hit1']:.3f}  merge auc {res['t3']['merge_auc']:.3f}", flush=True)
        if scifact is not None:
            cache = cache_by_id.setdefault(mid, {})
            res["t2"] = task_t2(model, qp, dp, *scifact, cache)
            print(f"  T2 ndcg@10 {res['t2']['ndcg10']:.3f}  ({res['t2']['seconds']} s)", flush=True)
        f.write_text(json.dumps(res, indent=1), encoding="utf-8")
        del model
        if not any(m[1] == mid for m in todo[k + 1:]):
            cache_by_id.pop(mid, None)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
