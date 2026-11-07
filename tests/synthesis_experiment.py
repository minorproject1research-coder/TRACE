"""Experiment: can the judge decide that SEVERAL partial findings TOGETHER answer an aspect? (Loop 2 improvement, 2026-11-08)

Why: after Loop 2 the aspects still uncovered are mostly not "no evidence" cases but near misses: 9 of 13 in the Q3/Q2/Q4 full runs have 3 or
more yes/partial verdicts from 2 or more sources (for example 10 partial verdicts from 10 sources for "how does 4-bit affect representation
and computation"). The coverage rule needs two single claims that each answer the whole aspect; a paper states one measured result, so a broad
aspect never gets two. More searching does not fix that.

What it does: for every aspect with yes/partial findings from at least 2 different sources, ONE judge item is built: the aspect, the claims of
up to 6 of those findings (yes first, then partial) as a numbered list, and their quotes numbered the same way. The judge (judge-v2, host) says
whether claim and quotes answer the aspect. Controls: the same composite built from the findings of an aspect of ANOTHER run (a different
topic) put under this aspect's text. Real judge, no database writes, temp verdict cache.

Pass rules, written before the first run:
  (1) negative controls: at most 10% "yes";
  (2) positives: the composites rated "yes" are read by me, and at least 80% of them truly answer the aspect from the claims shown;
  (3) the invented aspects of Q3 (diversity, security, interoperability) are not accepted.
Output: reports/synthesis_experiment.json and a table.

Variant v2 (2026-11-08, after reading the "partial" reasons of v1: several said the quote does not contain the summary framing "Taken together"):
the claim is just the numbered claims (no added framing), only findings whose quote the judge already found to support the claim are put in,
and the composite counts when the judge's `answers_aspect` is "yes" (support of each claim by its quote was checked one by one before).
Same controls and rules. Run with --v2; output reports/synthesis_experiment_v2.json.

Usage:  python tests/synthesis_experiment.py [--v2]
"""
import hashlib
import json
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from apps.api.agents.stage3_summarizer import evidence_judge as ej  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402

RUNS = {"Q3": "7c8e355e-122b-46b6-b227-44d876e9da1c", "Q2": "b24a57ac-fdcf-4802-ac29-c35297bcd7de", "Q4": "7ce198b5-0fb6-432c-a071-8c9711226ff1"}
MAX_CLAIMS = 6
V2 = "--v2" in sys.argv


def retry(fn):
    for _ in range(6):
        try:
            return fn()
        except Exception:
            time.sleep(2)
    raise SystemExit("database")


def composite(aspect, evid):
    claims = " ".join(f"({i}) {e['claim'].strip()}" for i, e in enumerate(evid, 1))
    quotes = " ".join(f"[{i}] {e['quote'].strip()}" for i, e in enumerate(evid, 1))
    return {"id": hashlib.sha256((aspect + claims).encode()).hexdigest()[:16], "aspect_idx": 0, "source_id": "synthesis", "aspect": aspect,
            "claim": claims if V2 else f"Taken together, these findings from different sources answer the question: {claims}", "quote": quotes, "context": ""}


def judge(items):
    verdicts = ej.judge_candidates(items) if items else {}
    out = []
    for it in items:
        key = (0, "synthesis", hashlib.sha256(it["claim"].encode()).hexdigest()[:16])
        out.append(verdicts.get(key, {}).get("verdict", {}))
    return out


def main() -> int:
    ej.JUDGE_CACHE_PATH = Path(tempfile.mkdtemp()) / "judge_cache.json"
    pools = []          # (run, sq topic, aspect text, [evidence], covered?)
    for name, qid in RUNS.items():
        sqs = sorted(retry(lambda: supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data), key=lambda r: r["created_at"])
        digs = retry(lambda: supabase.table("digests").select("sub_question_id,source_id,findings").eq("query_id", qid).execute().data)
        covs = retry(lambda: supabase.table("coverage_results").select("*").eq("query_id", qid).execute().data)
        for sq in sqs:
            unc = set([x for x in covs if x["sub_question_id"] == sq["id"]][-1].get("uncovered_aspects") or [])
            per = defaultdict(lambda: {"text": "", "yes": [], "partial": []})
            for d in digs:
                if d["sub_question_id"] != sq["id"]:
                    continue
                for f in d["findings"] or []:
                    for k, v in (f.get("judge") or {}).items():
                        if isinstance(v, dict) and v.get("final") in ("yes", "partial"):
                            per[int(k)]["text"] = v.get("aspect", "")
                            if V2 and v.get("quote_supports_claim") != "yes":
                                continue
                            per[int(k)][v["final"]].append({"source": d["source_id"], "claim": f["claim"], "quote": f["quote"]})
            for k, p in per.items():
                ev, seen = [], set()
                for e in p["yes"] + p["partial"]:
                    if e["source"] in seen:
                        continue
                    seen.add(e["source"])
                    ev.append(e)
                if len(ev) >= 2:
                    pools.append((name, sq["main_topic"], p["text"], ev[:MAX_CLAIMS], p["text"] not in unc))
    print(len(pools), "aspects with findings from at least 2 sources")

    pos = [composite(a, ev) for _, _, a, ev, _ in pools]
    neg = []
    for i, (name, _, a, ev, _) in enumerate(pools):
        other = next(p for p in pools[i + 1:] + pools[:i] if p[0] != name)           # an aspect of another run = another topic
        neg.append(composite(a, other[3]))
    vp, vn = judge(pos), judge(neg)
    rows = []
    for (name, sq, a, ev, covered), v, n in zip(pools, vp, vn):
        key = "answers_aspect" if V2 else "final"
        rows.append({"run": name, "sub_question": sq, "aspect": a, "covered_before": covered, "sources": len(ev), "synthesis": v.get(key),
                     "control": n.get(key), "claims": [e["claim"] for e in ev], "reason": v.get("reason")})
        print(f"{name} {'cov ' if covered else 'UNC '} synth={str(v.get(key)):7s} control={str(n.get(key)):7s} n={len(ev)}  {a[:75]}")
    (ROOT / "reports" / ("synthesis_experiment_v2.json" if V2 else "synthesis_experiment.json")).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    ctrl_yes = sum(1 for r in rows if r["control"] == "yes")
    print(f"\ncontrols rated yes: {ctrl_yes} of {len(rows)}")
    unc_rows = [r for r in rows if not r["covered_before"]]
    print(f"uncovered aspects accepted by synthesis: {sum(1 for r in unc_rows if r['synthesis'] == 'yes')} of {len(unc_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
