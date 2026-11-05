#!/usr/bin/env python3
"""
Experiment (handoff item 3): what changes if a finding may cover only ONE aspect (the aspect it is most similar to)?

Offline: no Groq and no judge calls. For the newest Stage 3 run of every sub-question of the audit queries it rebuilds the judge inputs from
the stored digests (findings.judge verdicts), then runs check_coverage_judged twice, ONE_FINDING_ONE_ASPECT off and on, and prints every
aspect whose state changes. Sanity check first: the flag-off reconstruction must give the same covered aspects as the stored coverage row.

  python tests/one_finding_one_aspect_experiment.py [--out reports/one_finding_one_aspect.json]
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
import audit_tag_precision as at  # noqa: E402
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder  # noqa: E402
from apps.api.agents.stage3_summarizer import coverage_check as cc  # noqa: E402
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic  # noqa: E402
from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects, run_merge_mode  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402


def covered_set(result, n):
    uncovered = set(result["uncovered_aspects"]) | set(result["unjudged_aspects"])
    return uncovered


def rebuild(sq, digests, embedder, merge_mode=None):
    aspects, a2d = flatten_aspects(sq["detail_questions"], sq["id"], _clean_topic(sq["main_topic"]), merge_mode=merge_mode)
    at.check_split_matches_run(sq["id"], aspects, digests)
    rows, verdicts, candidates = [], {}, []
    claims = [f["claim"] for d in digests for f in d["findings"] if f.get("judge")]
    emb = embedder.encode(claims + aspects, normalize_embeddings=True) if claims else None
    ci = 0
    for d in digests:
        rows.append({"source_id": d["source_id"], "evidence_level": d.get("evidence_level") or "full_text", "findings": d["findings"]})
        for f_idx, f in enumerate(d["findings"]):
            if not f.get("judge"):
                continue
            sims = emb[ci] @ emb[len(claims):].T
            ci += 1
            for a_str, v in f["judge"].items():
                a = int(a_str)
                if a >= len(aspects):
                    continue
                key = (a, d["source_id"], hashlib.sha256(f["claim"].encode()).hexdigest()[:16])
                verdicts[key] = {"verdict": {k: v.get(k) for k in ("final", "quote_supports_claim", "answers_aspect", "reason")}}
                candidates.append({"aspect_idx": a, "source_id": d["source_id"], "claim": f["claim"], "quote": f["quote"],
                                   "item_id": f"{d['source_id']}:{f_idx}:{a}", "similarity": float(sims[a])})
    return aspects, a2d, rows, verdicts, candidates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/one_finding_one_aspect.json")
    ap.add_argument("--export-dropped", action="store_true",
                    help="also write the dropped yes verdicts as a blind CSV (+ verdicts JSON) so they can be labeled")
    args = ap.parse_args()
    embedder = get_embedder()
    report, changed_total, aspects_total, mismatches = [], 0, 0, 0
    dropped_rows = []
    for qid in at.AUDIT_QUERY_IDS:
        for sq in supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data:
            digests = at.latest_generation(supabase.table("digests").select("*").eq("sub_question_id", sq["id"]).execute().data)
            stored = sorted(at.latest_generation(supabase.table("coverage_results").select("*").eq("sub_question_id", sq["id"]).execute().data),
                            key=lambda c: c["created_at"])[-1]
            aspects, a2d, rows, verdicts, candidates = rebuild(sq, digests, embedder, merge_mode=run_merge_mode(stored))
            results = {}
            for flag in ("false", "true"):
                os.environ["ONE_FINDING_ONE_ASPECT"] = flag
                results[flag] = cc.check_coverage_judged(aspects, a2d, sq["detail_questions"], rows, verdicts, candidates=candidates)
            off, on = results["false"], results["true"]
            stored_covered = at.covered_indices(stored, len(aspects))
            rebuilt_covered = {i for i, a in enumerate(aspects) if a not in covered_set(off, len(aspects))}
            if stored_covered != rebuilt_covered:
                mismatches += 1
                print(f"  CHECK FAILED {sq['id'][:8]}: rebuilt covered {sorted(rebuilt_covered)} != stored {sorted(stored_covered)}")
            covered_on = {i for i, a in enumerate(aspects) if a not in covered_set(on, len(aspects))}
            changed = sorted(rebuilt_covered - covered_on)
            aspects_total += len(aspects)
            changed_total += len(changed)
            yes_off = {i: len(off["aspect_evidence"].get(i, [])) for i in range(len(aspects))}
            yes_on = {i: len(on["aspect_evidence"].get(i, [])) for i in range(len(aspects))}
            print(f"\n{sq['id'][:8]} {sq['main_topic'][:60]}  sufficient off={off['sufficient']} on={on['sufficient']}  "
                  f"yes dropped={on['judge_stats'].get('one_finding_one_aspect_dropped')}")
            for i, a in enumerate(aspects):
                mark = "  <-- COVERED -> UNCOVERED" if i in changed else ""
                print(f"   [{i}] yes {yes_off[i]} -> {yes_on[i]}  {'covered' if i in rebuilt_covered else 'uncovered'} -> "
                      f"{'covered' if i in covered_on else 'uncovered'}  {a[:60]}{mark}")
            # the individual yes verdicts the rule drops (for labeling): yes keys before vs after assign_best_aspect
            yes_all = {i: sorted(k for k in verdicts if k[0] == i and verdicts[k]["verdict"]["final"] == "yes") for i in range(len(aspects))}
            sims = {(c["aspect_idx"], c["source_id"], hashlib.sha256(c["claim"].encode()).hexdigest()[:16]): c["similarity"] for c in candidates}
            kept, _ = cc.assign_best_aspect(yes_all, sims)
            cand_by_key = {(c["aspect_idx"], c["source_id"], hashlib.sha256(c["claim"].encode()).hexdigest()[:16]): c for c in candidates}
            for a, keys in yes_all.items():
                for k in keys:
                    if k in kept[a]:
                        continue
                    winner = next(a2 for a2, ks in kept.items() if any(kk[1:] == k[1:] for kk in ks))
                    c = cand_by_key[k]
                    dropped_rows.append({"query_id": qid, "sub_question_id": sq["id"], "main_topic": sq["main_topic"], "aspect_idx": a,
                                         "aspect_text": aspects[a], "source_id": k[1], "claim": c["claim"], "quote": c["quote"],
                                         "_kept_for_aspect": winner, "_kept_for_text": aspects[winner], "_sim_here": c["similarity"],
                                         "_sim_kept": sims[(winner, k[1], k[2])]})
            report.append({"sub_question_id": sq["id"], "topic": sq["main_topic"], "sufficient_off": off["sufficient"], "sufficient_on": on["sufficient"],
                           "aspects": [{"idx": i, "text": a, "yes_off": yes_off[i], "yes_on": yes_on[i], "covered_off": i in rebuilt_covered,
                                        "covered_on": i in covered_on} for i, a in enumerate(aspects)],
                           "dropped": on["judge_stats"].get("one_finding_one_aspect_dropped")})
    if args.export_dropped:
        import csv
        from datetime import datetime
        dropped_rows.sort(key=lambda r: hashlib.sha256((r["sub_question_id"] + str(r["aspect_idx"]) + r["claim"]).encode()).hexdigest())
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        fields = ["row_id", "query_id", "sub_question_id", "main_topic", "aspect_idx", "aspect_text", "source_id", "claim", "quote", "label", "notes"]
        side = {}
        for i, r in enumerate(dropped_rows, start=1):
            r["row_id"] = str(i)
            side[r["row_id"]] = {k: v for k, v in r.items() if k.startswith("_") or k in ("sub_question_id", "aspect_idx", "source_id")}
        with open(f"reports/tag_audit_dropped_{stamp}.csv", "x", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(dropped_rows)
        with open(f"reports/tag_audit_dropped_verdicts_{stamp}.json", "x", encoding="utf-8") as f:
            json.dump(side, f, indent=2, ensure_ascii=False)
        print(f"wrote reports/tag_audit_dropped_{stamp}.csv ({len(dropped_rows)} dropped yes verdicts) + verdicts json")
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'=' * 60}\naspects: {aspects_total}  covered -> uncovered with the rule: {changed_total}  "
          f"sub-questions whose 'sufficient' changes: {sum(1 for r in report if r['sufficient_off'] != r['sufficient_on'])} of {len(report)}")
    print("reconstruction check vs stored coverage rows:", "OK" if not mismatches else f"{mismatches} sub-question(s) differ")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
