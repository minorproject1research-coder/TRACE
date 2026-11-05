"""Live check of the Loop 2 query step against the real model server (costs ~6 planner calls, ~25 s each).

Pass criteria, fixed before the first run (2026-11-05):
  P1  every call returns at least 2 usable plans out of 3;
  P2  every case ends with at least 3 new queries (after removing near-duplicates of the queries already tried);
  P3  in every case at least 2 of the returned queries contain a content word of the aspect itself (a rough check that the
      queries are about the gap and not about the whole question);
  P4  no returned query has bge cosine >= 0.90 with a tried query (holds by construction; checked as a sanity test).
Whether the new queries FIND better papers is NOT measured here; that needs the loop wired in and a labeled comparison.

Usage:  python tests/gap_queries_live_check.py            writes docs/reports/runs-style output to stdout and reports/gap_queries_live.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from apps.api.agents.stage1_planner import gap_queries  # noqa: E402
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder  # noqa: E402
from apps.api.services import trace_llm_service  # noqa: E402
from apps.api.services.text_norm import normalized_words  # noqa: E402

ANCHOR = "deep learning"
SQ_TRANSFORMERS = "What are transformers and how do they work?"
SQ_TRAINING = "How are SSMs and transformers trained and evaluated?"
SQ_COMPARE = "How do SSMs and transformers compare in training efficiency and long-sequence performance?"
TRIED_TRANSFORMERS = ["transformers overview deep learning", "transformers components and parameters deep learning",
                      "transformers advantages and limitations deep learning"]
TRIED_TRAINING = ["training and evaluation metrics for SSMs and transformers deep learning",
                  "computational and memory requirements for SSMs and transformers deep learning"]
TRIED_COMPARE = ["SSMs vs transformers comparison results deep learning", "SSMs vs transformers comparison theory deep learning",
                 "SSMs vs transformers challenges and limitations deep learning"]

CASES = [   # (label, aspect, sub-question, tried queries, anchor); the queries tried are the ones run 5 searched (logs/pipeline.log)
    ("A transformers: parameters", "What are the parameters of a transformer?", SQ_TRANSFORMERS, TRIED_TRANSFORMERS, ANCHOR),
    ("B transformers: limitations", "What are the limitations of transformers?", SQ_TRANSFORMERS, TRIED_TRANSFORMERS, ANCHOR),
    ("C training: metrics and benchmarks",
     "What are the common metrics and benchmarks for measuring training efficiency of SSMs and transformers?", SQ_TRAINING, TRIED_TRAINING, ANCHOR),
    ("D training: compute and memory",
     "What are the computational and memory requirements for training and inference of SSMs and transformers?", SQ_TRAINING, TRIED_TRAINING, ANCHOR),
    ("E comparison: transformer limits (phrase aspect)", "open challenges or limitations for transformers", SQ_COMPARE, TRIED_COMPARE, ANCHOR),
    ("F RAG creativity (sub-question assumed)",
     "How does retrieval-augmented generation constrain the creativity and diversity of large language models?",
     "What are the effects of retrieval-augmented generation on large language model outputs?", [], ""),
]


def main():
    embedder = get_embedder()
    results, ok = [], True
    for label, aspect, sub_question, tried, anchor in CASES:
        seen = {}

        def planner(question, n, temperature):
            seen["question"] = question
            seen["plans"] = trace_llm_service.decompose_many(question, n=n, temperature=temperature)
            return seen["plans"]
        t0 = time.time()
        queries = gap_queries.generate(aspect, sub_question, tried, anchor, planner=planner, embedder=embedder)
        secs = round(time.time() - t0, 1)
        raw = sorted({q for p in seen["plans"] for q in p["search_queries"]})
        aspect_words = normalized_words(aspect) - normalized_words(anchor) - {"common", "requirement", "limitation", "challenge", "open"}
        on_topic = [q for q in queries if aspect_words & normalized_words(q)]
        max_tried = 0.0
        if queries and tried:
            import numpy as np
            max_tried = float((embedder.encode(queries, normalize_embeddings=True) @ embedder.encode(tried, normalize_embeddings=True).T).max())
        p1, p2, p3, p4 = len(seen["plans"]) >= 2, len(queries) >= 3, len(on_topic) >= 2, max_tried < gap_queries.DUPLICATE_SIMILARITY
        ok &= p1 and p2 and p3 and p4
        print(f"\n=== {label}  ({secs}s)  plans={len(seen['plans'])}  distinct raw queries={len(raw)}  new={len(queries)}  "
              f"on-topic={len(on_topic)}  max cos to tried={max_tried:.2f}  P1-4={[p1, p2, p3, p4]}")
        print(f"    question sent to the planner: {seen['question']}")
        for q in queries:
            print(f"    -> {q}")
        results.append({"case": label, "aspect": aspect, "question": seen["question"], "plans": len(seen["plans"]), "raw_queries": raw,
                        "new_queries": queries, "on_topic": len(on_topic), "max_cosine_to_tried": round(max_tried, 3),
                        "seconds": secs, "P1_P4": [p1, p2, p3, p4]})
    (ROOT / "reports" / "gap_queries_live.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nALL CRITERIA MET" if ok else "\nSOME CRITERIA NOT MET")


if __name__ == "__main__":
    main()
