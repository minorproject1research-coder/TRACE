"""Step 2: pre-label candidates with a strong LLM, then merge human review.

  python -m evaluation.relevance_judge.prelabel                  # label -> dataset.jsonl + review_queue.csv
  python -m evaluation.relevance_judge.prelabel --apply-review   # merge human overrides from review_queue.csv

The labeler uses a richer rubric than the production judge prompt on purpose,
so benchmark labels are not just "what the small model would say".
Rows the labeler is unsure about (confidence < --review-below) go to review_queue.csv;
fill the human_relevant column (true/false) and re-run with --apply-review.
"""
import argparse
import csv
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .common import ABSTRACT_CHAR_LIMIT, parse_verdict, read_jsonl

load_dotenv()
HERE = Path(__file__).parent

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "nvidia": ("https://integrate.api.nvidia.com/v1/chat/completions", "NVIDIA_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b"),
}

LABELER_PROMPT = """You are an expert annotator building a ground-truth dataset for a literature-review system.

Decide whether a paper is RELEVANT to a research sub-question, using only the title and abstract.

Mark relevant = true only if the paper would be useful as direct evidence or a core reference when answering the sub-question: it studies the same problem, method, or phenomenon the sub-question asks about, or provides results/analysis that bear directly on it.
Mark relevant = false if it only shares keywords or a broad field, applies the topic as a minor ingredient to a different problem, or addresses a different problem entirely.

Sub-question: {sub_question}

Title: {title}
Abstract: {abstract}

Think about the paper's actual contribution, then answer with ONLY this JSON:
{{"relevant": true or false, "confidence": number between 0 and 1 (how sure you are of this label), "reason": "one short sentence"}}"""


def call_labeler(client: httpx.Client, provider: str, model: str, row: dict) -> dict | None:
    url, key_env, _ = PROVIDERS[provider]
    prompt = LABELER_PROMPT.format(sub_question=row["sub_question"], title=row["title"],
                                   abstract=row["abstract"][:ABSTRACT_CHAR_LIMIT])
    for attempt in range(4):
        try:
            r = client.post(url, headers={"Authorization": f"Bearer {os.environ[key_env]}"},
                            json={"model": model, "temperature": 0.0,
                                  "messages": [{"role": "user", "content": prompt}]})
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt * 3)
                continue
            r.raise_for_status()
            return parse_verdict(r.json()["choices"][0]["message"]["content"])
        except httpx.HTTPError:
            time.sleep(2 ** attempt * 2)
    return None


def label(provider: str, model: str, review_below: float):
    rows = read_jsonl(HERE / "candidates.jsonl")
    out_path = HERE / "dataset.jsonl"
    done = {r["id"]: r for r in read_jsonl(out_path)} if out_path.exists() else {}

    with httpx.Client(timeout=120) as client, out_path.open("a", encoding="utf-8") as f:
        for i, row in enumerate(rows, 1):
            if row["id"] in done:
                continue
            verdict = call_labeler(client, provider, model, row)
            if verdict is None:
                print(f"[{i}/{len(rows)}] {row['id']} labeler failed, skipping (re-run to retry)")
                continue
            row = {**row, "label": verdict, "label_source": f"llm:{model}"}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            done[row["id"]] = row
            print(f"[{i}/{len(rows)}] {row['id']} relevant={verdict['relevant']} conf={verdict['confidence']:.2f}")

    queue = [r for r in done.values() if r["label"]["confidence"] < review_below]
    with (HERE / "review_queue.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "sub_question", "title", "abstract", "llm_relevant", "llm_confidence",
                    "llm_reason", "human_relevant"])
        for r in sorted(queue, key=lambda r: r["label"]["confidence"]):
            w.writerow([r["id"], r["sub_question"], r["title"], r["abstract"],
                        r["label"]["relevant"], r["label"]["confidence"], r["label"]["reason"], ""])
    n_pos = sum(r["label"]["relevant"] for r in done.values())
    print(f"\n{len(done)} labeled ({n_pos} relevant / {len(done) - n_pos} not). "
          f"{len(queue)} rows queued for review in review_queue.csv")


def apply_review():
    path = HERE / "dataset.jsonl"
    rows = read_jsonl(path)
    overrides = {}
    with (HERE / "review_queue.csv").open(encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            v = rec["human_relevant"].strip().lower()
            if v in ("true", "false"):
                overrides[rec["id"]] = v == "true"
    changed = 0
    for r in rows:
        if r["id"] in overrides:
            if r["label"]["relevant"] != overrides[r["id"]]:
                changed += 1
            r["label"]["relevant"] = overrides[r["id"]]
            r["label_source"] = "human"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"Applied {len(overrides)} human labels ({changed} flipped the LLM label)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=PROVIDERS, default="groq")
    ap.add_argument("--model", help="override the provider's default labeler model")
    ap.add_argument("--review-below", type=float, default=0.75)
    ap.add_argument("--apply-review", action="store_true")
    a = ap.parse_args()
    if a.apply_review:
        apply_review()
    else:
        label(a.provider, a.model or PROVIDERS[a.provider][2], a.review_below)
