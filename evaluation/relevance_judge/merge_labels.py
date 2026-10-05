"""Merge hand-written labels/batch*.jsonl into dataset.jsonl and report class balance.

  python -m evaluation.relevance_judge.merge_labels
"""
import json
import statistics
from collections import Counter
from pathlib import Path

from .common import read_jsonl

HERE = Path(__file__).parent
LABEL_SOURCE = "claude-manual"


def main():
    candidates = read_jsonl(HERE / "candidates.jsonl")
    labels = {}
    for f in sorted((HERE / "labels").glob("batch*.jsonl")):
        for row in read_jsonl(f):
            if row["id"] in labels:
                raise SystemExit(f"duplicate label for {row['id']} in {f.name}")
            labels[row["id"]] = row

    ids = {c["id"] for c in candidates}
    missing, extra = sorted(ids - labels.keys()), sorted(labels.keys() - ids)
    if missing or extra:
        raise SystemExit(f"missing labels: {missing}\nunknown ids: {extra}")

    rows = []
    for c in candidates:
        lab = labels[c["id"]]
        if not isinstance(lab["relevant"], bool) or not 0 <= lab["confidence"] <= 1 or not lab["reason"].strip():
            raise SystemExit(f"invalid label: {lab}")
        rows.append({**c, "label": {"relevant": lab["relevant"], "confidence": lab["confidence"],
                                    "reason": lab["reason"]}, "label_source": LABEL_SOURCE})

    (HERE / "dataset.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    pos = sum(r["label"]["relevant"] for r in rows)
    print(f"{len(rows)} rows -> dataset.jsonl | relevant {pos} ({pos / len(rows):.0%}) / not relevant {len(rows) - pos}")
    conf = [r["label"]["confidence"] for r in rows]
    print(f"confidence: median {statistics.median(conf):.2f} | <0.7: {sum(c < 0.7 for c in conf)} | <0.6: {sum(c < 0.6 for c in conf)}")
    per_q = Counter()
    for r in rows:
        per_q[r["sub_question_id"]] += r["label"]["relevant"]
    print("relevant per sub-question: min", min(per_q.values()), "max", max(per_q.values()),
          "| all-relevant questions:", [q for q, n in per_q.items() if n == 12],
          "| none-relevant:", [q for q, n in per_q.items() if n == 0])
    sims = {True: [], False: []}
    for r in rows:
        sims[r["label"]["relevant"]].append(r["embedding_similarity"])
    print("embedding similarity: relevant median %.2f | not relevant median %.2f" %
          (statistics.median(sims[True]), statistics.median(sims[False])))


if __name__ == "__main__":
    main()
