#!/usr/bin/env python3
"""
Audit of Stage 3 evidence (tags and judge verdicts).

MODE export:
  python tests/audit_tag_precision.py export [--query-ids a,b,c] [--n 50] [--seed 11]
Writes TWO new files with a unique timestamp (never overwrites a labeled file):
  reports/tag_audit_export_<seed>_<yyyymmdd_hhmm>.csv      -> what a human / LLM labels (NO judge information, NO covering basis)
  reports/tag_audit_verdicts_<seed>_<yyyymmdd_hhmm>.json   -> keyed by row_id: kind, covering_basis, judge verdict, ids

  kind (JSON only): covering | tagged | untagged
  covering_basis (JSON only):
      judge_yes : the judge's final verdict for this (finding, aspect) is "yes" AND the aspect is covered in the stored coverage
      tag_full  : the generator tagged it strength "full" and the judge did NOT rate it yes (or never judged it)
      none      : neither
  CSV `kind` is only tagged / untagged (generator metadata), so the labeler cannot see the judge's verdict.

Only the LATEST Stage 3 run per sub-question is used: every re-run appends new digests/coverage_results rows, so reading all rows
of a query mixes runs and includes stale findings.

MODE score:
  python tests/audit_tag_precision.py score --in reports/<labeled>.csv
"""
import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_N = 50
DEFAULT_SEED = 11
AUDIT_QUERY_IDS = [
    "6e0ccec0-2109-4794-8063-f077c4eac548",
    "6e735eb6-4b79-4c7e-af41-c88adaeee8fe",
    "780ed8a5-8794-49df-97e2-4548bbe10aeb",
]
MIN_UNTAGGED = 5          # untagged findings with the highest similarity to some aspect
MIN_PARTIAL_NO_COVERED = 10   # judge partial/no findings for covered aspects
QUOTA_TAG_FULL = 6        # strength-full findings the judge did not rate yes
GENERATION_WINDOW_S = 180  # rows written by one Stage 3 run share (almost) the same created_at
TARGET_PRECISION_STRICT = 0.85
TARGET_PRECISION_LENIENT = 0.92
MIN_AUC_FOR_RAISE_THRESHOLD = 0.75
CSV_FIELDS = ["row_id", "kind", "query_id", "sub_question_id", "main_topic", "aspect_text", "strength",
              "claim", "quote", "similarity", "label", "notes"]

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------- pure helpers (no DB, testable)

def _ts(value: str) -> datetime:
    return datetime.fromisoformat(str(value)[:19])


def latest_generation(rows: List[Dict], key: str = "sub_question_id") -> List[Dict]:
    """Per sub-question keep only the rows of the newest run (created_at within GENERATION_WINDOW_S of the newest row)."""
    newest: Dict[str, datetime] = {}
    for r in rows:
        t = _ts(r["created_at"])
        if r[key] not in newest or t > newest[r[key]]:
            newest[r[key]] = t
    return [r for r in rows if (newest[r[key]] - _ts(r["created_at"])).total_seconds() <= GENERATION_WINDOW_S]


def tag_strength(finding: Dict, aspect_idx: int) -> Optional[str]:
    """Strength of the generator's tag of this finding for aspect_idx (0-based), or None when the finding is not tagged for it."""
    for tag in finding.get("answers_details") or []:
        detail = tag.get("detail") if isinstance(tag, dict) else tag
        if detail == aspect_idx + 1:
            return tag.get("strength", "partial") if isinstance(tag, dict) else "partial"
    return None


def classify(final: Optional[str], strength: Optional[str], aspect_covered: bool) -> Tuple[str, str]:
    """(kind, covering_basis) for one (finding, aspect) pair."""
    if final == "yes" and aspect_covered:
        return "covering", "judge_yes"
    if strength == "full":
        return "tagged", "tag_full"
    return ("tagged" if strength else "untagged"), "none"


def round_robin(items: List[Dict], group_key, quota: int, rng: random.Random) -> List[Dict]:
    """Take up to `quota` items, cycling over the groups (shuffled) so every group is represented before any repeats."""
    groups: Dict[Any, List[Dict]] = defaultdict(list)
    for it in items:
        groups[group_key(it)].append(it)
    keys = list(groups)
    rng.shuffle(keys)
    for g in groups.values():
        rng.shuffle(g)
    out: List[Dict] = []
    while len(out) < quota and any(groups.values()):
        for k in keys:
            if groups[k] and len(out) < quota:
                out.append(groups[k].pop())
    return out


def sample_pool(pool: List[Dict], n: int, seed: int) -> List[Dict]:
    """Stratified sample. pool items: dict with kind, covering_basis, final, query_id, aspect_text, finding_key, has_any_tag, max_sim_untagged.

    Quotas (in this order): >= MIN_UNTAGGED untagged findings with the highest similarity to some aspect (spread over queries);
    >= MIN_PARTIAL_NO_COVERED judge partial/no findings on covered aspects; QUOTA_TAG_FULL tag_full rows; the rest judge_yes rows
    stratified by query and aspect. A finding is used at most once per aspect and at most twice overall."""
    rng = random.Random(seed)
    used_pairs, per_finding = set(), defaultdict(int)
    chosen: List[Dict] = []

    def take(candidates: List[Dict], group_key, quota: int):
        fresh = [c for c in candidates if (c["finding_key"], c["aspect_text"]) not in used_pairs and per_finding[c["finding_key"]] < 2]
        for c in round_robin(fresh, group_key, quota, rng):
            if (c["finding_key"], c["aspect_text"]) in used_pairs or per_finding[c["finding_key"]] >= 2:
                continue
            used_pairs.add((c["finding_key"], c["aspect_text"]))
            per_finding[c["finding_key"]] += 1
            chosen.append(c)

    untagged = sorted([p for p in pool if p["kind"] == "untagged_candidate"], key=lambda p: -p["similarity_val"])
    by_query: Dict[str, List[Dict]] = defaultdict(list)
    for u in untagged:
        by_query[u["query_id"]].append(u)
    picked_untagged: List[Dict] = []
    for i in range(MIN_UNTAGGED + 1):          # top-similarity first, one query after the other
        for q in by_query:
            if i < len(by_query[q]) and len(picked_untagged) < MIN_UNTAGGED + 1:
                picked_untagged.append(by_query[q][i])
    take(picked_untagged, lambda c: c["query_id"], MIN_UNTAGGED + 1)

    partial_no = [p for p in pool if p["kind"] != "untagged_candidate" and p["aspect_covered"] and p["final"] in ("partial", "no")]
    take(partial_no, lambda c: (c["query_id"], c["aspect_text"]), MIN_PARTIAL_NO_COVERED + 2)

    tag_full = [p for p in pool if p["covering_basis"] == "tag_full" and p["kind"] != "untagged_candidate"]
    take(tag_full, lambda c: (c["query_id"], c["aspect_text"]), QUOTA_TAG_FULL)

    yes_rows = [p for p in pool if p["covering_basis"] == "judge_yes"]
    take(yes_rows, lambda c: (c["query_id"], c["aspect_text"]), max(0, n - len(chosen)))
    rng.shuffle(chosen)
    return chosen


def build_outputs(chosen: List[Dict]) -> Tuple[List[Dict], Dict[str, Dict]]:
    """Blind CSV rows + JSON sidecar keyed by row_id."""
    csv_rows, sidecar = [], {}
    for i, c in enumerate(chosen, start=1):
        rid = str(i)
        is_untagged = c["kind"] in ("untagged", "untagged_candidate") or c["strength"] == ""
        csv_rows.append({
            "row_id": rid, "kind": "untagged" if is_untagged else "tagged", "query_id": c["query_id"],
            "sub_question_id": c["sub_question_id"], "main_topic": c["main_topic"], "aspect_text": c["aspect_text"],
            "strength": c["strength"], "claim": c["claim"], "quote": c["quote"], "similarity": f"{c['similarity_val']:.4f}",
            "label": "", "notes": "",
        })
        sidecar[rid] = {
            "kind": "untagged" if c["kind"] == "untagged_candidate" else c["kind"],
            "covering_basis": c["covering_basis"], "final": c["final"] or "",
            "quote_supports_claim": c.get("quote_supports_claim") or "", "answers_aspect": c.get("answers_aspect") or "",
            "reason": c.get("reason") or "", "aspect_covered": c["aspect_covered"], "aspect_idx": c["aspect_idx"],
            "query_id": c["query_id"], "sub_question_id": c["sub_question_id"], "source_id": c["source_id"],
            "digest_id": c.get("digest_id"), "finding_idx": c["finding_idx"],
        }
    return csv_rows, sidecar


def assert_consistent(csv_rows: List[Dict], sidecar: Dict[str, Dict], n_min: int) -> Dict[str, Any]:
    """Hard checks before anything is written; returns the counts that get printed."""
    assert [r["row_id"] for r in csv_rows] == list(sidecar.keys()), "CSV rows and JSON rows differ"
    assert len({r["row_id"] for r in csv_rows}) == len(csv_rows), "duplicate row ids"
    assert not any(k in csv_rows[0] for k in ("final", "covering_basis", "judge", "verdict")), "judge columns leaked into the CSV"
    for rid, s in sidecar.items():
        if s["covering_basis"] == "judge_yes":
            assert s["final"] == "yes" and s["aspect_covered"], f"row {rid}: judge_yes without a yes verdict on a covered aspect"
        if s["final"] == "yes" and s["aspect_covered"]:
            assert s["covering_basis"] == "judge_yes", f"row {rid}: judge yes on a covered aspect not marked judge_yes"
    counts = {
        "rows": len(csv_rows),
        "per_query": dict(sorted(_count(s["query_id"] for s in sidecar.values()).items())),
        "per_kind": _count(s["kind"] for s in sidecar.values()),
        "per_covering_basis": _count(s["covering_basis"] for s in sidecar.values()),
        "per_verdict": _count((s["final"] or "unjudged") for s in sidecar.values()),
    }
    assert counts["rows"] >= n_min, f"only {counts['rows']} rows (need {n_min})"
    assert len(counts["per_query"]) == len(AUDIT_QUERY_IDS), f"queries represented: {list(counts['per_query'])}"
    assert counts["per_kind"].get("untagged", 0) >= MIN_UNTAGGED, "fewer than 5 untagged rows"
    covered_partial_no = sum(1 for s in sidecar.values() if s["aspect_covered"] and s["final"] in ("partial", "no"))
    assert covered_partial_no >= MIN_PARTIAL_NO_COVERED, f"only {covered_partial_no} judge partial/no rows on covered aspects"
    counts["covered_aspect_partial_or_no"] = covered_partial_no
    return counts


def _count(values) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for v in values:
        out[v] += 1
    return dict(out)


# ---------------------------------------------------------------- DB part

class SplitMismatch(RuntimeError):
    """Today's aspect split has fewer aspects than the stored run used (verdicts exist for a higher aspect index)."""


def check_split_matches_run(sq_id: str, aspects: List[str], digests: List[Dict]) -> None:
    """Aspect splits are LLM output and the aspect cache can be lost, so today's split may not be the one a stored run was judged
    against. Verdicts are stored per aspect INDEX; if one exists beyond today's aspect list, the indices no longer line up and any
    audit built on them would be wrong. Fail loudly instead of silently dropping those verdicts."""
    used = [int(k) for d in digests for f in d.get("findings") or [] for k in (f.get("judge") or {})]
    if used and max(used) >= len(aspects):
        raise SplitMismatch(f"sub-question {sq_id[:8]}: the stored run has verdicts for aspect index {max(used)} but today's split has only "
                            f"{len(aspects)} aspects. Restore the aspect cache entries of that run before auditing.")


def covered_indices(cov: Dict, n_aspects: int) -> set:
    """Aspect indices that were covered in a stored coverage row. Decided by INDEX from aspect_evidence (>= JUDGE_MIN_YES yes verdicts from
    >= 2 distinct sources), never by aspect text: the stored texts come from an LLM split that changes between runs."""
    evidence = cov.get("aspect_evidence") or {}
    out = set()
    for i in range(n_aspects):
        ev = evidence.get(str(i)) or evidence.get(i) or []
        yes = [e for e in ev if e.get("verdict") == "yes"]
        if len(yes) >= 2 and len({e.get("source_id") for e in yes}) >= 2:
            out.add(i)
    return out


def check_alignment(sq_id: str, aspects: List[str], cov: Dict, embedder, min_sim: float = 0.85) -> None:
    """Warn when an aspect named in the stored coverage row (uncovered / unjudged text) has no close match in today's aspect list, i.e.
    today's split differs from the run's and aspect INDICES may no longer line up."""
    stored = list(cov.get("uncovered_aspects") or []) + list(cov.get("unjudged_aspects") or [])
    if not stored or not aspects:
        return
    emb = embedder.encode(stored + aspects, normalize_embeddings=True)
    sims = emb[:len(stored)] @ emb[len(stored):].T
    for k, text in enumerate(stored):
        if float(sims[k].max()) < min_sim:
            print(f"  WARNING sub-question {sq_id[:8]}: stored aspect has no close match in today's split (max sim {float(sims[k].max()):.2f}): {text[:70]}")



def collect_pool(query_ids: List[str]) -> List[Dict]:
    from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
    from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic
    from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects, run_merge_mode
    from apps.api.services.db_service import supabase

    embedder = get_embedder()
    pool: List[Dict] = []
    for qid in query_ids:
        sqs = supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data
        digests = latest_generation(supabase.table("digests").select("*").eq("query_id", qid).execute().data)
        covs = supabase.table("coverage_results").select("*").eq("query_id", qid).execute().data
        covs = {c["sub_question_id"]: c for c in latest_generation(covs)}
        print(f"query {qid[:8]}: {len(sqs)} sub-questions, {len(digests)} digests in the latest run(s)")
        for sq in sqs:
            topic = _clean_topic(sq.get("main_topic", ""))
            cov = covs.get(sq["id"], {})
            aspects, _ = flatten_aspects(sq.get("detail_questions", []), sq["id"], topic, merge_mode=run_merge_mode(cov))
            sq_digests_all = [d for d in digests if d["sub_question_id"] == sq["id"]]
            check_split_matches_run(sq["id"], aspects, sq_digests_all)
            covered_idx = covered_indices(cov, len(aspects))
            check_alignment(sq["id"], aspects, cov, embedder)
            sq_digests = [d for d in digests if d["sub_question_id"] == sq["id"]]
            claims, meta = [], []
            for d in sq_digests:
                for f_idx, f in enumerate(d.get("findings") or []):
                    if f.get("verified") and f.get("claim") and f.get("quote"):
                        claims.append(f["claim"])
                        meta.append((d, f_idx, f))
            if not claims or not aspects:
                continue
            emb = embedder.encode(claims + aspects, normalize_embeddings=True)
            sims = emb[:len(claims)] @ emb[len(claims):].T
            for i, (d, f_idx, f) in enumerate(meta):
                fkey = f"{d['id']}:{f_idx}"
                judged = f.get("judge") or {}
                base = {"query_id": qid, "sub_question_id": sq["id"], "main_topic": sq.get("main_topic", ""), "source_id": d["source_id"],
                        "digest_id": d.get("id"), "finding_idx": f_idx, "claim": f["claim"], "quote": f["quote"], "finding_key": fkey}
                any_tag = False
                for a_idx, a_text in enumerate(aspects):
                    strength = tag_strength(f, a_idx)
                    verdict = judged.get(str(a_idx))
                    if strength is None and verdict is None:
                        continue
                    any_tag = any_tag or strength is not None
                    covered = a_idx in covered_idx
                    a_text = (verdict or {}).get("aspect") or a_text      # the text the judge saw, when it was stored
                    final = (verdict or {}).get("final")
                    kind, basis = classify(final, strength, covered)
                    pool.append({**base, "kind": kind, "covering_basis": basis, "aspect_idx": a_idx, "aspect_text": a_text,
                                 "strength": strength or "", "final": final, "aspect_covered": covered,
                                 "quote_supports_claim": (verdict or {}).get("quote_supports_claim"),
                                 "answers_aspect": (verdict or {}).get("answers_aspect"), "reason": (verdict or {}).get("reason"),
                                 "similarity_val": float(sims[i][a_idx])})
                if not any_tag and not judged:      # the generator tagged it for nothing and the judge never saw it
                    best = int(sims[i].argmax())
                    pool.append({**base, "kind": "untagged_candidate", "covering_basis": "none", "aspect_idx": best,
                                 "aspect_text": aspects[best], "strength": "", "final": None,
                                 "aspect_covered": best in covered_idx, "similarity_val": float(sims[i][best])})
    return pool


def export_mode(args):
    query_ids = [q.strip() for q in args.query_ids.split(",")] if args.query_ids else AUDIT_QUERY_IDS
    pool = collect_pool(query_ids)
    print(f"pool: {len(pool)} (finding, aspect) pairs; judge_yes={sum(p['covering_basis']=='judge_yes' for p in pool)} "
          f"tag_full={sum(p['covering_basis']=='tag_full' for p in pool)} untagged_candidates={sum(p['kind']=='untagged_candidate' for p in pool)}")
    chosen = sample_pool(pool, args.n, args.seed)
    csv_rows, sidecar = build_outputs(chosen)
    counts = assert_consistent(csv_rows, sidecar, n_min=min(args.n, 45))

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = Path(args.out_dir) / f"tag_audit_export_{args.seed}_{stamp}.csv"
    out_json = Path(args.out_dir) / f"tag_audit_verdicts_{args.seed}_{stamp}.json"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "x", newline="", encoding="utf-8") as f:       # "x": refuse to overwrite an existing file
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(csv_rows)
    with open(out_json, "x", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)

    # read back and re-check what was actually written
    with open(out_csv, "r", encoding="utf-8-sig", newline="") as f:
        back = list(csv.DictReader(f))
    assert [r["row_id"] for r in back] == list(json.load(open(out_json, encoding="utf-8")).keys())
    assert not any("â€" in (r["claim"] + r["quote"]) for r in back), "mojibake in the export"
    print(f"\nwrote {out_csv}\nwrote {out_json}")
    print(json.dumps(counts, indent=2))
    print("\nNext: label the 'label' column (1 / 0.5 / 0), then: python tests/audit_tag_precision.py score --in <labeled csv>")


# ---------------------------------------------------------------- scoring (unchanged logic)

def compute_auc(label1_sims: List[float], label0_sims: List[float]) -> float:
    if not label1_sims or not label0_sims:
        return 0.0
    pairs = correct = 0
    for s1 in label1_sims:
        for s0 in label0_sims:
            pairs += 1
            correct += 1 if s1 > s0 else (0.5 if s1 == s0 else 0)
    return correct / pairs if pairs else 0.5


def score_mode(args):
    input_path = Path(args.in_file)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return
    with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("No rows in input file")
        return
    tagged = [r for r in rows if r["kind"] != "untagged"]      # old files also have kind=covering
    labeled = []
    for r in tagged:
        try:
            r["label_val"] = float(r["label"]) if r["label"] else None
        except ValueError:
            r["label_val"] = None
        if r["label_val"] is not None:
            labeled.append(r)
    print(f"\n{'=' * 60}\nTAG PRECISION SCORE\n{'=' * 60}")
    print(f"Total tagged rows: {len(tagged)}  labeled: {len(labeled)}  skipped (empty label): {len(tagged) - len(labeled)}")
    if not labeled:
        print("No labeled rows to score")
        return
    strict = sum(1 for r in labeled if r["label_val"] == 1.0) / len(labeled)
    lenient = sum(1 for r in labeled if r["label_val"] >= 0.5) / len(labeled)
    print(f"Strict precision (label==1): {strict:.3f}\nLenient precision (label>=0.5): {lenient:.3f}")
    for strength in ("full", "partial"):
        sr = [r for r in labeled if r.get("strength") == strength]
        if sr:
            print(f"Strength '{strength}' (n={len(sr)}): strict={sum(r['label_val'] == 1.0 for r in sr) / len(sr):.3f}, "
                  f"lenient={sum(r['label_val'] >= 0.5 for r in sr) / len(sr):.3f}")
    l1 = [float(r["similarity"]) for r in labeled if r["label_val"] == 1.0]
    l0 = [float(r["similarity"]) for r in labeled if r["label_val"] == 0.0]
    auc = compute_auc(l1, l0)
    print(f"AUC (similarity, label 1 vs 0): {auc:.3f}")
    passed = strict >= TARGET_PRECISION_STRICT and lenient >= TARGET_PRECISION_LENIENT
    print(f"{'PASS' if passed else 'FAIL'}: strict={strict:.3f} (need >= {TARGET_PRECISION_STRICT}), lenient={lenient:.3f} (need >= {TARGET_PRECISION_LENIENT})")
    sys.exit(0 if passed else 1)


def main():
    parser = argparse.ArgumentParser(description="Audit Stage 3 evidence")
    sub = parser.add_subparsers(dest="mode", required=True)
    pe = sub.add_parser("export")
    pe.add_argument("--query-ids", help="comma-separated; default = the 3 audit queries")
    pe.add_argument("--n", type=int, default=DEFAULT_N)
    pe.add_argument("--seed", type=int, default=DEFAULT_SEED)
    pe.add_argument("--out-dir", default="reports")
    ps = sub.add_parser("score")
    ps.add_argument("--in", dest="in_file", required=True)
    args = parser.parse_args()
    export_mode(args) if args.mode == "export" else score_mode(args)


if __name__ == "__main__":
    main()
