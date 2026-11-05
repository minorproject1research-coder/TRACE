#!/usr/bin/env python3
"""
Re-judge the stored Stage 3 runs with the judge that is deployed NOW (JUDGE_MODEL_ID names it) and compare coverage with the stored run.

For the newest run of every sub-question of the 3 audit queries it takes exactly the (finding, aspect) pairs that were judged in the stored run
and judges them again, in two ways:
  ctx    with the CORRECT surrounding passage (rebuilt from the same source: build_chunks(paper)[chunk_id], or the web snippet)
  noctx  with no passage
The stored run's verdicts ("stored") were made by the older judge AND with another paper's passage (chunk ids repeat in every source; fixed 2026-11-04),
so ctx versus stored shows the combined effect of the new prompt and the fix, ctx versus noctx isolates the passage.

Real judge calls, no database writes. Two cache files (a verdict does not depend on the passage in the cache key, so ctx and noctx must not share one).

  python tests/rejudge_stage3.py [--out reports/rejudge_stage3.json]
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
import audit_tag_precision as at  # noqa: E402
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder  # noqa: E402
from apps.api.agents.stage3_summarizer import chunk_selector, coverage_check as cc, evidence_judge as ej  # noqa: E402
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic  # noqa: E402
from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects, run_merge_mode  # noqa: E402
from apps.api.services import db_service  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402

LABELED = [  # labeled csv, verdicts/ids sidecar json (row_id -> sub_question_id, aspect_idx, source_id)
    ("reports/tag_audit_labeled_targeted.csv", "reports/tag_audit_targeted_verdicts_20261104_2154.json"),
    ("reports/tag_audit_labeled_dropped.csv", "reports/tag_audit_dropped_verdicts_20261104_2209.json"),
    ("reports/tag_audit_labeled_heldout.csv", "reports/tag_audit_verdicts_11_20261104_2153.json"),
]
PRED = {"yes": 1.0, "partial": 0.5, "no": 0.0}


def h(claim: str) -> str:
    return hashlib.sha256(claim.encode()).hexdigest()[:16]


def load_labels():
    """(sub_question_id, aspect_idx, source_id) -> list of (label, labeled aspect text, claim)"""
    out = defaultdict(list)
    for csv_path, side_path in LABELED:
        if not (Path(csv_path).exists() and Path(side_path).exists()):
            continue
        side = json.load(open(side_path, encoding="utf-8"))
        for r in csv.DictReader(open(csv_path, encoding="utf-8-sig", newline="")):
            s = side.get(r["row_id"])
            if s and r.get("label", "") != "":
                out[(s["sub_question_id"], int(s["aspect_idx"]), str(s["source_id"]))].append((float(r["label"]), r["aspect_text"], r["claim"], Path(csv_path).stem))
    return out


def source_text(sources, source_id, chunk_id):
    kind, obj = sources.get(source_id, (None, None))
    if kind == "paper":
        chunks = chunk_selector.build_chunks(obj)
        return chunks[chunk_id] if isinstance(chunk_id, int) and 0 <= chunk_id < len(chunks) else ""
    if kind == "web":
        return obj.get("snippet") or ""
    return ""


def coverage(aspects, a2d, details, rows, verdicts, cands, rule=False, margin=0.0):
    os.environ["ONE_FINDING_ONE_ASPECT"] = "true" if rule else "false"
    os.environ["ONE_FINDING_MARGIN"] = str(margin)
    return cc.check_coverage_judged(aspects, a2d, details, rows, verdicts, candidates=cands)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/rejudge_stage3.json")
    args = ap.parse_args()
    cfg = ej._get_config()
    if not cfg["JUDGE_URL"]:
        print("ERROR: no judge URL (TRACE_LLM_URL). Nothing was run.")
        return 2
    print(f"REAL judge | endpoint {cfg['JUDGE_URL'].split('//')[-1]} | JUDGE_MODEL_ID={cfg['JUDGE_MODEL_ID']} | no database writes")
    tmp = Path(tempfile.mkdtemp(prefix="rejudge_"))
    embedder = get_embedder()
    labels = load_labels()
    per_sq, pairs_all = [], []

    for qid in at.AUDIT_QUERY_IDS:
        for sq in supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data:
            digests = at.latest_generation(supabase.table("digests").select("*").eq("sub_question_id", sq["id"]).execute().data)
            stored_cov = sorted(at.latest_generation(supabase.table("coverage_results").select("*").eq("sub_question_id", sq["id"]).execute().data),
                                key=lambda c: c["created_at"])[-1]
            aspects, a2d = flatten_aspects(sq["detail_questions"], sq["id"], _clean_topic(sq["main_topic"]), merge_mode=run_merge_mode(stored_cov))
            at.check_split_matches_run(sq["id"], aspects, digests)
            sources = {str(p["id"]): ("paper", p) for p in db_service.get_papers_for_stage3(qid, sq["id"])}
            sources.update({str(w["id"]): ("web", w) for w in db_service.get_web_sources_for_stage3(sq["id"])})

            rows, stored, cands, lookup = [], {}, [], {}
            for d in digests:
                rows.append({"source_id": d["source_id"], "evidence_level": d.get("evidence_level") or "full_text", "findings": d["findings"]})
                for f_idx, f in enumerate(d["findings"]):
                    for a_str, entry in (f.get("judge") or {}).items():
                        a = int(a_str)
                        if a >= len(aspects) or not f.get("verified"):
                            continue
                        text = entry.get("aspect") or aspects[a]
                        cid = f.get("chunk_id")
                        lookup[f"{d['source_id']}:{cid}"] = source_text(sources, str(d["source_id"]), cid)
                        emb = embedder.encode([f["claim"], text], normalize_embeddings=True)
                        cands.append({"aspect_idx": a, "aspect_text": text, "source_id": d["source_id"], "claim": f["claim"], "quote": f["quote"],
                                      "chunk_id": cid, "similarity": float(emb[0] @ emb[1]), "digest_idx": 0, "finding_idx": f_idx,
                                      "item_id": hashlib.sha256(f"{text}|{d['source_id']}|{f_idx}".encode()).hexdigest()[:16]})
                        stored[(a, d["source_id"], h(f["claim"]))] = {"verdict": {k: entry.get(k) for k in ("final", "quote_supports_claim", "answers_aspect", "reason")}}
            if not cands:
                continue
            items = ej.build_judge_items(cands, lookup)
            missing_ctx = sum(1 for i in items if not i["context"])
            result = {}
            for mode in ("ctx", "noctx"):
                batch = [dict(i, context=(i["context"] if mode == "ctx" else "")) for i in items]
                ej.JUDGE_CACHE_PATH = tmp / f"cache_{mode}.json"
                result[mode] = ej.judge_candidates(batch)
            cov = {"stored": coverage(aspects, a2d, sq["detail_questions"], rows, stored, cands),
                   "ctx": coverage(aspects, a2d, sq["detail_questions"], rows, result["ctx"], cands),
                   "noctx": coverage(aspects, a2d, sq["detail_questions"], rows, result["noctx"], cands),
                   "ctx_rule": coverage(aspects, a2d, sq["detail_questions"], rows, result["ctx"], cands, rule=True, margin=0.05)}
            os.environ["ONE_FINDING_ONE_ASPECT"] = "false"
            covered = {m: {i for i, a in enumerate(aspects) if a not in set(c["uncovered_aspects"]) | set(c["unjudged_aspects"])} for m, c in cov.items()}
            yes = {m: {i: len(c["aspect_evidence"].get(i, [])) for i in range(len(aspects))} for m, c in cov.items()}
            per_sq.append({"sub_question_id": sq["id"], "topic": sq["main_topic"], "aspects": aspects, "pairs": len(cands), "pairs_without_passage": missing_ctx,
                           "covered": {m: sorted(v) for m, v in covered.items()}, "yes": yes, "sufficient": {m: c["sufficient"] for m, c in cov.items()},
                           "errors": {m: sum(1 for v in result[m].values() if v["verdict"]["final"] not in PRED) for m in ("ctx", "noctx")}})
            for c in cands:
                k = (c["aspect_idx"], c["source_id"], h(c["claim"]))
                pairs_all.append({"sq": sq["id"], "aspect_idx": c["aspect_idx"], "aspect_text": c["aspect_text"], "source_id": c["source_id"], "claim": c["claim"],
                                  "stored": stored[k]["verdict"]["final"], "ctx": result["ctx"][k]["verdict"]["final"], "noctx": result["noctx"][k]["verdict"]["final"]})
            print(f"{sq['id'][:8]} pairs={len(cands):<3} no-passage={missing_ctx:<2} covered stored/ctx/noctx/ctx+rule = "
                  f"{len(covered['stored'])}/{len(covered['ctx'])}/{len(covered['noctx'])}/{len(covered['ctx_rule'])} of {len(aspects)}  sufficient "
                  f"{cov['stored']['sufficient']}/{cov['ctx']['sufficient']}/{cov['noctx']['sufficient']}/{cov['ctx_rule']['sufficient']}")

    # ---- summary
    print(f"\n{'=' * 78}\nPAIRS ({len(pairs_all)}): verdict counts")
    for m in ("stored", "ctx", "noctx"):
        print(f"  {m:<7}", dict(Counter(p[m] for p in pairs_all)))
    print("  stored -> ctx transitions:", dict(sorted(Counter(f"{p['stored']}->{p['ctx']}" for p in pairs_all).items())))
    print("  ctx vs noctx differ on", sum(1 for p in pairs_all if p["ctx"] != p["noctx"]), "pairs")
    n_asp = sum(len(s["aspects"]) for s in per_sq)
    print(f"\nASPECTS ({n_asp}) covered: " + "  ".join(f"{m}={sum(len(s['covered'][m]) for s in per_sq)}" for m in ("stored", "ctx", "noctx", "ctx_rule")))
    print("SUB-QUESTIONS sufficient: " + "  ".join(f"{m}={sum(1 for s in per_sq if s['sufficient'][m])}/{len(per_sq)}" for m in ("stored", "ctx", "noctx", "ctx_rule")))
    print("\nASPECTS whose covered state differs from the stored run (stored -> ctx):")
    for s in per_sq:
        for i, a in enumerate(s["aspects"]):
            st, cx, nx, rl = (i in s["covered"][m] for m in ("stored", "ctx", "noctx", "ctx_rule"))
            if st != cx or st != nx or cx != rl:
                print(f"  {s['sub_question_id'][:8]} [{i}] yes {s['yes']['stored'][i]}->{s['yes']['ctx'][i]} (noctx {s['yes']['noctx'][i]}, +rule {s['yes']['ctx_rule'][i]}) "
                      f"stored {'cov' if st else 'UNC'} ctx {'cov' if cx else 'UNC'} noctx {'cov' if nx else 'UNC'} ctx+rule {'cov' if rl else 'UNC'}  {a[:55]}")

    # ---- labeled subset: how right is each version on rows I labeled?
    print(f"\nLABELED PAIRS (my labels; rows whose aspect wording still matches today's split)")
    by_pair = {(p["sq"], p["aspect_idx"], str(p["source_id"])): p for p in pairs_all}
    rows_l, skipped = [], 0
    for key, lst in labels.items():
        p = by_pair.get(key)
        if p is None:
            skipped += len(lst)
            continue
        for lab, text, claim, src in lst:
            if h(claim) != h(p["claim"]):
                skipped += 1
                continue
            e = embedder.encode([text, p["aspect_text"]], normalize_embeddings=True)
            if float(e[0] @ e[1]) < 0.85:
                skipped += 1
                continue
            rows_l.append({**p, "label": lab, "file": src})
    uniq = {(r["sq"], r["aspect_idx"], r["source_id"], h(r["claim"])): r for r in rows_l}
    rows_l = list(uniq.values())
    print(f"  usable {len(rows_l)} unique pairs (skipped {skipped} labeled rows: not judged in the stored run or aspect wording differs)")
    for m in ("stored", "ctx", "noctx"):
        yes = [r for r in rows_l if r[m] == "yes"]; ones = [r for r in rows_l if r["label"] == 1]
        s = sum(r["label"] == 1 for r in yes); l = sum(r["label"] >= .5 for r in yes); rec = sum(r[m] == "yes" for r in ones)
        agree = sum(PRED[r[m]] == r["label"] for r in rows_l) / len(rows_l) if rows_l else 0
        print(f"  {m:<7} yes={len(yes):<3} strict {s}/{len(yes)}={s / max(len(yes), 1):.3f}  lenient {l}/{len(yes)}={l / max(len(yes), 1):.3f}  recall {rec}/{len(ones)}={rec / max(len(ones), 1):.3f}  agreement {agree:.2f}  false-yes(label 0)={sum(r['label'] == 0 for r in yes)}")
    Path(args.out).write_text(json.dumps({"judge_model_id": cfg["JUDGE_MODEL_ID"], "sub_questions": per_sq, "pairs": pairs_all, "labeled": rows_l}, indent=2, ensure_ascii=False, default=list), encoding="utf-8")
    print(f"\nsaved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
