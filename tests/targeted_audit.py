#!/usr/bin/env python3
"""
Targeted audit (handoff item 2): EVERY judge-"yes" finding for the aspects suspected of over-coverage.

  memory cost defined / measured / factors    sub-question 763a1e90 (aspects 2, 3, 4)
  basic components of LLMs                    sub-question b4ff92b2 (aspect 0)
  motivation of RAG                           sub-question e96996ab (aspect 0)
  attention degradation, computational cx     sub-question cdf8f029 (aspects 0, 1)

Writes (unique timestamp, never overwrites):
  reports/tag_audit_targeted_<yyyymmdd_hhmm>.csv            for labeling: aspect, full claim, full quote, source id, item id; NO judge columns
  reports/tag_audit_targeted_verdicts_<yyyymmdd_hhmm>.json  keyed by row_id: judge fields + which OTHER aspects the same finding was also "yes" for

Only the newest Stage 3 run per sub-question is used. Aspect text is the text stored with the verdict when present (runs after
2026-11-04), otherwise today's split at the same index (checked against the stored uncovered-aspect texts; see check_alignment).

  python tests/targeted_audit.py [--out-dir reports]
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

# sub-question id -> {aspect index: keyword that must appear in that aspect's text (guards against an index shift)}
TARGETS = {
    "763a1e90": {2: "memory cost is defined", 3: "memory cost is measured", 4: "factors"},
    "b4ff92b2": {0: "components"},
    "e96996ab": {0: "motivation"},
    "cdf8f029": {0: "attention", 1: "complexity"},
}
CSV_FIELDS = ["row_id", "query_id", "sub_question_id", "main_topic", "aspect_idx", "aspect_text", "source_id", "item_id", "claim", "quote",
              "label", "notes"]


def build_rows(digests, sq, aspects, targets):
    """All (finding, aspect) pairs with judge final == yes (verified findings only) for the target aspects of one sub-question."""
    rows = []
    for d in digests:
        for f_idx, f in enumerate(d.get("findings") or []):
            if not f.get("verified"):
                continue
            judged = f.get("judge") or {}
            for a_idx, keyword in targets.items():
                v = judged.get(str(a_idx))
                if not v or v.get("final") != "yes":
                    continue
                text = v.get("aspect") or aspects[a_idx]
                assert keyword.lower() in text.lower(), f"{sq['id']} aspect {a_idx}: expected '{keyword}' in '{text}' (aspect index shifted?)"
                item_id = hashlib.sha256(f"{text}|{d['source_id']}|{f_idx}".encode()).hexdigest()[:16]
                rows.append({
                    "query_id": sq["query_id"], "sub_question_id": sq["id"], "main_topic": sq["main_topic"], "aspect_idx": a_idx,
                    "aspect_text": text, "source_id": d["source_id"], "item_id": item_id, "claim": f["claim"], "quote": f["quote"],
                    "_judge": {k: v.get(k) for k in ("final", "quote_supports_claim", "answers_aspect", "reason")},
                    "_digest_id": d.get("id"), "_finding_idx": f_idx,
                    "_also_yes_for_aspects": sorted(int(k) for k, vv in judged.items() if vv.get("final") == "yes" and int(k) != a_idx),
                    "_tag_strength": next((t.get("strength") for t in f.get("answers_details") or []
                                           if isinstance(t, dict) and t.get("detail") == a_idx + 1), None),
                })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
    from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic
    from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects, run_merge_mode
    from apps.api.services.db_service import supabase
    import audit_tag_precision as at

    embedder = get_embedder()
    all_rows, per_aspect_total = [], defaultdict(int)
    for sid, targets in TARGETS.items():
        sq = supabase.table("sub_questions").select("*").eq("id", sid).execute().data[0]
        digests = at.latest_generation(supabase.table("digests").select("*").eq("sub_question_id", sid).execute().data)
        cov = sorted(at.latest_generation(supabase.table("coverage_results").select("*").eq("sub_question_id", sid).execute().data),
                     key=lambda c: c["created_at"])[-1]
        aspects, _ = flatten_aspects(sq["detail_questions"], sq["id"], _clean_topic(sq["main_topic"]), merge_mode=run_merge_mode(cov))
        at.check_split_matches_run(sid, aspects, digests)
        at.check_alignment(sid, aspects, cov, embedder)
        rows = build_rows(digests, sq, aspects, targets)
        for r in rows:
            per_aspect_total[(sid, r["aspect_idx"])] += 1
        all_rows.extend(rows)

    all_rows.sort(key=lambda r: hashlib.sha256(r["item_id"].encode()).hexdigest())      # fixed but unrelated-to-topic order, so the labeler sees mixed rows
    for i, r in enumerate(all_rows, start=1):
        r["row_id"] = str(i)
    csv_rows = [{k: r.get(k, "") for k in CSV_FIELDS} for r in all_rows]
    sidecar = {r["row_id"]: {"sub_question_id": r["sub_question_id"], "aspect_idx": r["aspect_idx"], "item_id": r["item_id"],
                             "source_id": r["source_id"], "digest_id": r["_digest_id"], "finding_idx": r["_finding_idx"],
                             "tag_strength": r["_tag_strength"], "also_yes_for_aspects": r["_also_yes_for_aspects"], **r["_judge"]}
               for r in all_rows}

    # checks before writing
    assert [c["row_id"] for c in csv_rows] == list(sidecar), "CSV and JSON rows differ"
    assert all(s["final"] == "yes" for s in sidecar.values()), "a non-yes finding got into the audit"
    assert not any(k in csv_rows[0] for k in ("final", "judge", "verdict", "reason", "also_yes_for_aspects")), "judge columns leaked into the CSV"
    assert len({r["item_id"] for r in csv_rows}) == len(csv_rows), "duplicate item ids"

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = Path(args.out_dir) / f"tag_audit_targeted_{stamp}.csv"
    out_json = Path(args.out_dir) / f"tag_audit_targeted_verdicts_{stamp}.json"
    with open(out_csv, "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(csv_rows)
    with open(out_json, "x", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
    with open(out_csv, "r", encoding="utf-8-sig", newline="") as f:
        assert len(list(csv.DictReader(f))) == len(all_rows)

    print(f"wrote {out_csv}\nwrote {out_json}\nrows: {len(all_rows)}")
    for (sid, a), n in sorted(per_aspect_total.items()):
        print(f"  {sid} aspect {a}: {n} yes finding(s)")
    missing = [(sid, a) for sid, t in TARGETS.items() for a in t if per_aspect_total.get((sid, a), 0) == 0]
    if missing:
        print(f"  no yes findings at all for: {missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
