"""Does adding the topic as an aspect (TOPIC_ASPECT) reduce the findings the digest model returns?  Real Groq calls, no database writes.

Why: the first run through the API (2026-11-06, mixture-of-experts question) had 104 findings in 40 digests, against 146 on 2026-11-05, and the
same 22 sources gave 3.74 findings per digest before and 2.35 after; 0 of 5 sub-questions were sufficient instead of 4. That run changed several
things at once (topic aspect, quote verifier, query gate, plan cache, new Groq responses). This script isolates the topic aspect: the same
sources, the same code, only the aspect list differs, each condition run twice to measure the run-to-run spread.

Pre-registered rule (2026-11-06, before the first call): the topic aspect is harmful to digests if the mean number of findings per digest with it
is at least 20% lower than without it AND the gap is larger than the spread between the two repeats of the same condition.

Usage:  python tests/topic_aspect_digest_experiment.py [query_id]      (default: the 2026-11-06 API run)
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from apps.api.agents.stage3_summarizer import chunk_selector, detail_aspects as da, digest_generator  # noqa: E402
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic  # noqa: E402
from apps.api.services import db_service  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402

QID = "abb1db57-d2bd-4a76-b80f-89981ae68563"
SUB_QUESTIONS = 2          # the first two sub-questions of the run
PAPERS_EACH = 3


def digest(sq, paper, aspects):
    chunks = chunk_selector.build_chunks(paper)
    selected = chunk_selector.select_chunks(sq["main_topic"], chunks, detail_questions=aspects, main_topic=_clean_topic(sq["main_topic"]))
    findings = digest_generator.generate_digest(sq["main_topic"], selected, detail_aspects=aspects, main_topic=_clean_topic(sq["main_topic"]),
                                                cache_scope=None, strict=False)
    return {"chunks": len(selected), "chars": sum(len(t) for _, t in selected), "findings": len(findings), "verified": sum(1 for f in findings if f["verified"])}


def main():
    qid = sys.argv[1] if len(sys.argv) > 1 else QID
    sqs = sorted(supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data, key=lambda s: s["created_at"])[:SUB_QUESTIONS]
    results = []
    for sq in sqs:
        base, a2d = da.flatten_aspects(sq["detail_questions"], sq["id"], _clean_topic(sq["main_topic"]), merge_mode="exact")
        with_topic, _, _ = da.with_topic_aspect(base, a2d, sq["detail_questions"], sq["main_topic"], enabled=True)
        for p in db_service.get_papers_for_stage3(qid, sq["id"])[:PAPERS_EACH]:
            row = {"sub_question": sq["main_topic"], "paper": (p.get("title") or "")[:60]}
            for label, aspects in (("no_topic_1", base), ("topic_1", with_topic), ("no_topic_2", base), ("topic_2", with_topic)):
                row[label] = digest(sq, p, aspects)
            results.append(row)
            print(f"{row['paper']:60s} " + "  ".join(f"{k}={row[k]['findings']}f/{row[k]['chunks']}c" for k in ("no_topic_1", "no_topic_2", "topic_1", "topic_2")), flush=True)
    mean = lambda label: sum(r[label]["findings"] for r in results) / len(results)
    m_nt = (mean("no_topic_1") + mean("no_topic_2")) / 2
    m_t = (mean("topic_1") + mean("topic_2")) / 2
    spread = abs(mean("no_topic_1") - mean("no_topic_2"))
    chunks = lambda label: sum(r[label]["chunks"] for r in results) / len(results)
    print(f"\nsources {len(results)} | findings per digest: no topic {mean('no_topic_1'):.2f} / {mean('no_topic_2'):.2f} (mean {m_nt:.2f}), "
          f"topic {mean('topic_1'):.2f} / {mean('topic_2'):.2f} (mean {m_t:.2f}) | spread between repeats {spread:.2f} | change {100 * (m_t - m_nt) / m_nt:+.0f}%")
    print(f"chunks per digest: no topic {chunks('no_topic_1'):.1f}, topic {chunks('topic_1'):.1f}")
    harmful = m_t <= 0.8 * m_nt and (m_nt - m_t) > spread
    print("RULE: topic aspect reduces findings:", "YES (harmful)" if harmful else "NO")
    (ROOT / "reports" / "topic_aspect_digest_experiment.json").write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
