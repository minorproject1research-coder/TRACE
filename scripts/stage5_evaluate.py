"""Evaluation checks of the Stage 5 written report, on STORED reports (no search, no Stage 3 or 4 work, no Groq tokens).

  venv/Scripts/python.exe scripts/stage5_evaluate.py --run <query_id> [--run <query_id> ...] [--audit 100] [--corrupt 40] [--out DIR] [--seed 42]

Three checks:

  A. Citation check (deterministic, every body sentence): the reference numbers of a sentence are mapped back to documents and compared with the
     documents of the quotes of its claims. citation precision = cited documents that hold a quote of one of the sentence's claims / cited documents;
     citation recall = documents the sentence's claims stand on / of those, the cited ones. Also: markers valid, no [n] or URL in the text, and the
     source count of the tier (single: exactly one document; partly: two; supported: two or more).
  B. Audit sample (default 100 sentences, stratified by tier): every sampled sentence with the claims, the quotes, the deterministic checks and the
     NLI entailment of the quotes -> sentence (the judge is switched OFF, so this is stricter than the pipeline). Written as a sheet with an empty
     column "human verdict" for a person; the machine columns are NOT a human review.
  C. Corrupted-copy test: sentences of the report are damaged on purpose (a number changed, an invented name, the hedge removed or upgraded, a citation
     marker, another section's claim ids, a negation flipped, an unrelated sentence, an antonym) and the same checks as in the pipeline must reject
     the copy. Detection rate per corruption; the clean sentences are the control (false-reject rate).

Outputs: PATH/eval_<run>.json, PATH/audit_sheet.md and PATH/summary.md (default reports/stage5/eval, not committed). Loads the NLI model of Stage 4.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NO_JUDGE = lambda claim, quote: {"supports": False, "confidence": 0.0, "reason": "audit: judge switched off"}      # noqa: E731


# ------------------------------------------------------------------------------------------------------------------------------ loading
def load_run(run: str, row=None, inputs=None, report_json=None):
    """(report dict, claims_by_id) of a stored run; `report_json` = a file written by stage5_on_stored_run.py (its "report") instead of the stored row."""
    from apps.api.agents.stage5_report import loader, tiers
    from apps.api.services import db_service
    if report_json:
        import json
        data = json.load(open(report_json, encoding="utf-8"))
        row = {"report": data.get("report", data)}
    row = row or db_service.get_written_report(run)
    if not row:
        raise SystemExit(f"run {run}: no stored written report")
    inputs = inputs or loader.load_inputs(run)
    claims = tiers.build_claims(inputs["sub_questions"], scope_on=False)
    return row["report"], {c.claim_id: c for c in claims}


def body_sentences(report: dict) -> list:
    out = []
    for si, sec in enumerate(report["sections"]):
        for s in sec["sentences"]:
            out.append({**s, "section": si, "section_title": sec["title"]})
    return out


# ------------------------------------------------------------------------------------------------------------------------------ A. citations
def _keys_of(claims: list, relations: tuple) -> set:
    return {e.ref_key for c in claims for e in c.evidence if e.relation in relations}


def expected_keys(tier: str, claims: list) -> set:
    from apps.api.agents.stage5_report import tiers
    if tier == "single":                                       # the document the claim stands on
        return {e.ref_key for e in (tiers.primary_evidence(c) for c in claims) if e is not None}
    if tier == "partly":
        return _keys_of(claims, ("supports", "near_match"))
    return _keys_of(claims, ("supports",))


def citation_check(report: dict, claims_by_id: dict) -> dict:
    sid2key = {e.source_id: e.ref_key for c in claims_by_id.values() for e in c.evidence}
    refs = {r["number"]: r for r in report["references"]}
    rows = []
    for s in body_sentences(report):
        claims = [claims_by_id[i] for i in s["claimIds"] if i in claims_by_id]
        cited = set()
        for n in s["refs"]:
            for sid in (refs.get(n) or {}).get("sourceIds", []):
                if sid in sid2key:
                    cited.add(sid2key[sid])
        allowed = _keys_of(claims, ("supports", "near_match"))
        expected = expected_keys(s["tier"], claims)
        problems = []
        if len(claims) != len(s["claimIds"]):
            problems.append("unknown claim id")
        if any(n not in refs for n in s["refs"]):
            problems.append("reference number missing")
        if re.search(r"\[\d+", s["text"]) or re.search(r"https?://", s["text"]):
            problems.append("marker or URL in the text")
        n_docs = len(cited)
        if s["tier"] == "single" and n_docs != 1:
            problems.append(f"single-source sentence cites {n_docs} documents")
        if s["tier"] == "partly" and n_docs != 2:
            problems.append(f"partly supported sentence cites {n_docs} documents")
        if s["tier"] == "supported" and n_docs < 2:
            problems.append(f"supported sentence cites {n_docs} document(s)")
        rows.append({"precision": (len(cited & allowed) / len(cited)) if cited else 0.0, "recall": (len(expected & cited) / len(expected)) if expected else 1.0,
                     "problems": problems, "tier": s["tier"], "text": s["text"][:140]})
    n = len(rows) or 1
    by_tier = {}
    for t in ("supported", "partly", "single"):
        sub = [r for r in rows if r["tier"] == t]
        if sub:
            by_tier[t] = {"sentences": len(sub), "precision": round(sum(r["precision"] for r in sub) / len(sub), 4),
                          "recall": round(sum(r["recall"] for r in sub) / len(sub), 4), "with_problems": sum(1 for r in sub if r["problems"])}
    return {"sentences": len(rows), "precision": round(sum(r["precision"] for r in rows) / n, 4), "recall": round(sum(r["recall"] for r in rows) / n, 4),
            "with_problems": sum(1 for r in rows if r["problems"]), "by_tier": by_tier, "problem_examples": [r for r in rows if r["problems"]][:8]}


# ------------------------------------------------------------------------------------------------------------------------------ B. audit
def make_job(tier: str, claims: list):
    from apps.api.agents.stage5_report.schema import Job
    return Job(job_id="audit", section_id="audit", tier=tier, claims=claims)


def machine_verdict(s: dict, claims_by_id: dict, nli=None) -> dict:
    from apps.api.agents.stage5_report import grounding, validators
    claims = [claims_by_id[i] for i in s["claimIds"] if i in claims_by_id]
    job = make_job(s["tier"], claims)
    det = validators.check_sentence(s["text"], s["claimIds"], job)
    ok, detail = grounding.entails(s["text"], validators.evidence_texts(job, s["claimIds"]), nli=nli, judge=NO_JUDGE)
    return {"deterministic": det, "nli_ok": ok, "entailment": detail.get("entailment"), "contradiction": detail.get("contradiction"), "reason": detail.get("reason")}


def stratified(sentences: list, n: int, rng: random.Random) -> list:
    by = {}
    for s in sentences:
        by.setdefault(s["tier"], []).append(s)
    total = len(sentences)
    out = []
    for tier, items in sorted(by.items()):
        k = max(1, round(n * len(items) / total))
        out += rng.sample(items, min(k, len(items)))
    rng.shuffle(out)
    return out[:n]


def audit(sample: list, claims_by_id: dict, nli=None) -> list:
    rows = []
    for i, s in enumerate(sample, 1):
        v = machine_verdict(s, claims_by_id, nli)
        claims = [claims_by_id[c] for c in s["claimIds"] if c in claims_by_id]
        quotes = [(e.title[:60], e.relation, e.evidence_level, e.quote) for c in claims for e in c.evidence if e.relation != "contradicts"]
        rows.append({"n": i, "run": s.get("run"), "tier": s["tier"], "text": s["text"], "refs": s["refs"], "claims": [c.text for c in claims], "quotes": quotes, **v})
        print(f"  audit {i}/{len(sample)}: nli_ok={v['nli_ok']} det={bool(v['deterministic'])}", flush=True)
    return rows


# ------------------------------------------------------------------------------------------------------------------------------ C. corruption
_NEG = [(r"\b(is|are|was|were|can|does|do|has|have)\b(?! not)", r"\1 not"), (r"\bimproves?\b", "does not improve"), (r"\benables?\b", "prevents"),
        (r"\bprotects?\b", "exposes"), (r"\bpreserv(es|ing)\b", "destroys")]
_ANTONYM = [("higher", "lower"), ("lower", "higher"), ("better", "worse"), ("improves", "degrades"), ("reduces", "increases"), ("increases", "reduces"),
            ("comparable", "far inferior"), ("without", "with"), ("faster", "slower"), ("more", "fewer"), ("outperform", "underperform")]


def _swap_number(text: str):
    m = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
    if not m:
        return None
    v = float(m.group(1))
    new = str(int(v * 7 + 13)) if "." not in m.group(1) else f"{v * 3 + 1.7:.1f}"
    return text[:m.start()] + new + text[m.end():]


def _flip_negation(text: str):
    for pat, rep in _NEG:
        new, n = re.subn(pat, rep, text, count=1, flags=re.I)
        if n:
            return new
    return None


def _antonym(text: str):
    for a, b in _ANTONYM:
        if re.search(rf"\b{a}\b", text, flags=re.I):
            return re.sub(rf"\b{a}\b", b, text, count=1, flags=re.I)
    return None


def corruptions(s: dict, others: list, rng: random.Random) -> dict:
    """{name: (corrupted text, claim ids)} for the corruptions that apply to this sentence."""
    from apps.api.agents.stage5_report import hedging
    text, ids = s["text"], s["claimIds"]
    body = text.rstrip(".")
    out = {}
    if (t := _swap_number(text)):
        out["number_changed"] = (t, ids)
    out["invented_name"] = (body + ", and the HyperFedNet-3000 system of Zhao Labs confirmed this.", ids)
    out["citation_marker"] = (body + " [3].", ids)
    if s["tier"] in ("single", "partly"):
        stripped = hedging.strip_attribution(text)
        if stripped != text:
            out["hedge_removed"] = (stripped[:1].upper() + stripped[1:], ids)
            out["hedge_upgraded"] = ("It is well established that " + stripped[:1].lower() + stripped[1:], ids)
    foreign = [o for o in others if o["section"] != s["section"] and o["claimIds"]]
    if foreign:
        out["foreign_claim_id"] = (text, rng.choice(foreign)["claimIds"][:1])
        other = rng.choice(foreign)
        out["unrelated_sentence"] = (other["text"], ids)
    if (t := _flip_negation(text)):
        out["negation_flipped"] = (t, ids)
    if (t := _antonym(text)):
        out["antonym_swapped"] = (t, ids)
    return out


DETERMINISTIC = {"number_changed", "invented_name", "citation_marker", "hedge_removed", "hedge_upgraded", "foreign_claim_id"}


def corrupt_test(sample: list, all_sentences: list, claims_by_id: dict, per_nli: int, rng: random.Random, nli=None) -> dict:
    from apps.api.agents.stage5_report import grounding, validators
    res: dict = {}
    nli_used: dict = {}
    for k, s in enumerate(sample, 1):
        claims_all = {i: claims_by_id[i] for i in claims_by_id}
        for name, (text, ids) in corruptions(s, all_sentences, rng).items():
            if name not in DETERMINISTIC:
                if nli_used.get(name, 0) >= per_nli:
                    continue
                nli_used[name] = nli_used.get(name, 0) + 1
            job_claims = [claims_all[i] for i in s["claimIds"] if i in claims_all]       # the job is the ORIGINAL sentence's claims
            job = make_job(s["tier"], job_claims)
            reasons = validators.check_sentence(text, ids, job)
            layer = "deterministic" if reasons else None
            if not reasons and name not in DETERMINISTIC:
                ok, detail = grounding.entails(text, validators.evidence_texts(job, ids), nli=nli, judge=NO_JUDGE)
                if not ok:
                    reasons, layer = [detail.get("reason", "rejected")], "nli"
            r = res.setdefault(name, {"tested": 0, "detected": 0, "by_deterministic": 0, "by_nli": 0, "missed": []})
            r["tested"] += 1
            if reasons:
                r["detected"] += 1
                r["by_deterministic" if layer == "deterministic" else "by_nli"] += 1
            elif len(r["missed"]) < 4:
                r["missed"].append(text[:200])
        print(f"  corrupt {k}/{len(sample)}", flush=True)
    for r in res.values():
        r["rate"] = round(r["detected"] / r["tested"], 4) if r["tested"] else None
    return res


# ------------------------------------------------------------------------------------------------------------------------------ output
def write_sheet(path: Path, rows: list) -> None:
    lines = ["# Stage 5 audit sheet", "",
             "Machine columns come from the deterministic checks and from the NLI model (judge off). **They are not a human review.** "
             "Fill in `human verdict`: OK (the sentence says what its quotes say, with the right strength), TOO STRONG, WRONG, or UNSUPPORTED.", ""]
    for r in rows:
        lines += [f"## {r['n']}. [{r['tier']}] run {str(r.get('run'))[:8]}", "", f"> {r['text']}", "",
                  f"- machine: NLI {'accepted' if r['nli_ok'] else 'NOT accepted'} (entailment {r['entailment']}, contradiction {r['contradiction']}); "
                  f"deterministic checks: {'; '.join(r['deterministic']) if r['deterministic'] else 'passed'}", f"- cited references: {r['refs']}",
                  f"- claims: {' | '.join(r['claims'])}"]
        for title, rel, level, quote in r["quotes"][:4]:
            lines.append(f"- quote ({rel}, {level}, {title}): {quote[:420]}")
        lines += ["- **human verdict:** ", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evaluation checks of stored Stage 5 reports")
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--audit", type=int, default=100)
    ap.add_argument("--corrupt", type=int, default=40, help="sentences per NLI-based corruption (the deterministic ones use all audited sentences)")
    ap.add_argument("--out", default="reports/stage5/eval")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-nli", action="store_true", help="only the citation check (A)")
    ap.add_argument("--report-json", help="evaluate this report file (from stage5_on_stored_run.py --out) instead of the stored one; needs exactly one --run")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    summary, pool, claims_all = {}, [], {}
    for run in args.run:
        report, claims = load_run(run, report_json=args.report_json if len(args.run) == 1 else None)
        sents = [{**s, "run": run} for s in body_sentences(report)]
        pool += sents
        claims_all.update(claims)
        a = citation_check(report, claims)
        summary[run] = {"status": report["status"], "template_version": report.get("stats", {}).get("template_version"), "citations": a}
        print(f"run {run[:8]}: {a['sentences']} sentences, citation precision {a['precision']}, recall {a['recall']}, {a['with_problems']} with problems {a['by_tier']}")
        (out / f"eval_{run[:8]}.json").write_text(json.dumps(summary[run], indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    if args.skip_nli:
        return 0
    sample = stratified(pool, args.audit, rng)
    print(f"audit sample: {len(sample)} sentences")
    rows = audit(sample, claims_all)
    write_sheet(out / "audit_sheet.md", rows)
    clean = {"sentences": len(rows), "nli_accepted": sum(1 for r in rows if r["nli_ok"]), "deterministic_flagged": sum(1 for r in rows if r["deterministic"]),
             "by_tier": {}}
    for t in ("supported", "partly", "single"):
        sub = [r for r in rows if r["tier"] == t]
        if sub:
            clean["by_tier"][t] = {"sentences": len(sub), "nli_accepted": sum(1 for r in sub if r["nli_ok"])}
    summary["audit_clean"] = clean
    print("audit clean sentences:", clean)
    bad = corrupt_test(sample, pool, claims_all, args.corrupt, rng)
    summary["corruptions"] = bad
    for name, r in bad.items():
        print(f"  {name}: {r['detected']}/{r['tested']} rejected ({r['rate']}) deterministic {r['by_deterministic']} nli {r['by_nli']}")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    (out / "audit_rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
