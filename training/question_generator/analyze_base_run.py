"""Extra analysis of the finished base model run (docs/BASE_MODEL_EVALUATION.md, sections 4 and 5). Generates nothing; reads the checkpoint file.

    python analyze_base_run.py [SAMPLE]        SAMPLE = rows scored with the embedding model (default 600, about 5 minutes on a laptop CPU)

It uses the reader and the metric code of base_model_eval.ipynb (cells 7 and 8), so the counts here are those of the notebook's lenient score.
Part 1 (no model): topics, details and queries written against the reference, cut-off answers against finished ones, how topics are worded.
Part 2 (bge-base-en-v1.5, CPU): the similarity of a random sample, and a FLOOR: the same answers scored against the reference of ANOTHER question.
"""
import difflib
import json
import os
import random
import re
import statistics as st
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 600
RUN_TAG = "Qwen3.5-9B-Base_0shot"
MAX_NEW_TOKENS = 768

nb = json.load(open(HERE / "base_model_eval.ipynb", encoding="utf-8"))
ns = {"json": json, "re": re, "difflib": difflib, "np": np, "BACKEND": "vllm", "os": os}
metrics_cell = "".join(nb["cells"][7]["source"]).replace(
    'embedder = SentenceTransformer("BAAI/bge-base-en-v1.5", device="cpu" if BACKEND == "vllm" else None)', "embedder = None")
exec(metrics_cell, ns)                                   # metric code of model.ipynb, cell 49
exec("".join(nb["cells"][8]["source"]), ns)              # the lenient reader

rows = [json.loads(line) for line in open(HERE / f"eval_checkpoint_{RUN_TAG}.jsonl", encoding="utf-8") if line.strip()]
print("checkpoint rows", len(rows), "| unique questions", len({r["question"] for r in rows}))
info = []
for r in rows:
    plan, source = ns["lenient_plan"](r["generated_raw"])
    info.append({"r": r, "plan": plan, "source": source, "ref": ns["extract_json_from_output"](r["reference_raw"]), "cut": r["new_tokens"] >= MAX_NEW_TOKENS})
print("reader source:", dict(Counter(i["source"] for i in info)))


def count_block(name, subset):
    read = [i for i in subset if i["plan"] and i["ref"]]
    gt = [len(i["plan"]["sub_questions"]) for i in read]
    rt = [len(i["ref"]["sub_questions"]) for i in read]
    gq = [len(i["plan"]["search_queries"]) for i in read]
    rq = [len(i["ref"]["search_queries"]) for i in read]
    with_q = sum(1 for i in subset if i["plan"] and i["plan"]["search_queries"]) / len(subset)
    print(f"{name:22s} n={len(subset):5d} read={len(read):5d} topics written {st.mean(gt):.2f} reference {st.mean(rt):.2f} match {100 * sum(a == b for a, b in zip(gt, rt)) / len(read):5.1f}%"
          f" | queries written {st.mean(gq):.2f} reference {st.mean(rq):.2f} match {100 * sum(a == b for a, b in zip(gq, rq)) / len(read):5.1f}% | plans with queries {100 * with_q:.1f}%")
    return gt, rt


print("\n--- part 1: counts (no model) ---")
gt, rt = count_block("all answers", info)
count_block("cut at token limit", [i for i in info if i["cut"]])
count_block("finished under limit", [i for i in info if not i["cut"]])
print("topics written, distribution:", sorted(Counter(gt).items())[:10])
print("topics in reference, distribution:", sorted(Counter(rt).items())[:10])
print(f"answers with 4 to 6 topics: {100 * sum(1 for g in gt if 4 <= g <= 6) / len(gt):.1f}% | references with 3 to 4 topics: {100 * sum(1 for g in rt if 3 <= g <= 4) / len(rt):.1f}%")
print("detail questions per plan: written", round(st.mean(sum(len(s["details"]) for s in i["plan"]["sub_questions"]) for i in info if i["plan"]), 2),
      "| reference", round(st.mean(sum(len(s["details"]) for s in i["ref"]["sub_questions"]) for i in info if i["ref"]), 2))

topics_ref = [(s["topic"] if isinstance(s, dict) else str(s)) for i in info if i["ref"] for s in i["ref"]["sub_questions"]]
topics_base = [s["topic"] for i in info if i["plan"] for s in i["plan"]["sub_questions"]]
for name, topics in (("reference topics", topics_ref), ("topics read from the base answers", topics_base)):
    print(f"{name:34s} n={len(topics):6d} | end with '?': {100 * sum(t.strip().endswith('?') for t in topics) / len(topics):5.1f}% | mean words: {st.mean(len(t.split()) for t in topics):.1f}")
sys.stdout.flush()

print(f"\n--- part 2: similarity of a random sample of {SAMPLE} readable answers, with a floor (bge-base-en-v1.5 on the CPU) ---")
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-base-en-v1.5", device="cpu")
cache = {}


class CachedEmbedder:
    def encode(self, texts, normalize_embeddings=True):
        new = [t for t in dict.fromkeys(texts) if t not in cache]
        if new:
            for t, e in zip(new, model.encode(new, normalize_embeddings=True, batch_size=32)):
                cache[t] = e
        return np.stack([cache[t] for t in texts])


ns["embedder"] = CachedEmbedder()
readable = [k for k, i in enumerate(info) if i["plan"] and i["ref"]]
sample = random.Random(42).sample(readable, min(SAMPLE, len(readable)))
own, floor, cut, fin = [], [], [], []
t0 = time.time()
for n, k in enumerate(sample):
    i = info[k]
    other = info[sample[(n + 1) % len(sample)]]
    plan_json = json.dumps(i["plan"], ensure_ascii=False)
    ev = ns["evaluate_single"](i["r"]["question"], plan_json, i["r"]["reference_raw"])
    own.append(ev)
    floor.append(ns["evaluate_single"](i["r"]["question"], plan_json, other["r"]["reference_raw"]))     # the same answer against another question's reference
    (cut if i["cut"] else fin).append(ev)
    if n % 100 == 99:
        print(f"  {n + 1}/{len(sample)} rows, {time.time() - t0:.0f} s")
        sys.stdout.flush()


def report(name, evs):
    mean = lambda key: sum(e[key] for e in evs) / len(evs)      # noqa: E731
    print(f"{name:36s} n={len(evs):4d} topic {mean('topic_similarity'):.3f} details {mean('details_similarity'):.3f} query {mean('query_similarity'):.3f}")


report("answer vs its own reference", own)
report("answer vs another question's reference (floor)", floor)
report("  answers cut at the limit", cut)
report("  answers that finished", fin)
