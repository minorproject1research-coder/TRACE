"""Collect everything of ONE finished run into a folder (for a presentation, a report, a hand-in): the written report, the evidence report, the live events,
the numbers per stage and a traced example sentence (claim -> quote -> source).

  venv/Scripts/python.exe scripts/export_run_bundle.py --run <query_id> [--out reports/ppt_example] [--api http://localhost:8000]

Needs the API to be running. The session and the events of a run live in the API process memory (a restart keeps only what is in the database: no
timings, tokens or events), so export a run BEFORE restarting the API. Writes: README_facts.md (all numbers and the traced example), written_report.md/.json,
evidence_report.json, events.json (+ events_raw.txt), session.json. Nothing is written to the database.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

LABELS = {"supported": "supported", "partially_supported": "partly supported", "unverified": "unverified (one document states it)", "contradicted": "contradicted"}


def get(url: str, timeout: int = 60) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8")


def get_events(url: str) -> str:
    try:
        return get(url, timeout=8)
    except Exception as e:                      # the stream stays open: a timeout after the stored events were sent is the normal end
        return getattr(e, "partial", b"").decode("utf-8", "ignore") if hasattr(e, "partial") else ""


def parse_events(raw: str) -> list:
    out = []
    for blk in raw.split("\n\n"):
        m = re.search(r"^data: (.*)$", blk, flags=re.M)
        if m:
            try:
                out.append(json.loads(m.group(1)))
            except ValueError:
                pass
    return out


def secs(a: str, b: str) -> int:
    from datetime import datetime
    f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))        # noqa: E731
    return int((f(b) - f(a)).total_seconds())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Export one run as a folder of files")
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", default="reports/ppt_example")
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = f"{args.api}/api/research/{args.run}"

    session = json.loads(get(base))
    (out / "session.json").write_text(json.dumps(session, indent=1, ensure_ascii=False), encoding="utf-8")
    raw = get_events(base + "/events")
    (out / "events_raw.txt").write_text(raw, encoding="utf-8")
    events = parse_events(raw)
    (out / "events.json").write_text(json.dumps(events, indent=1, ensure_ascii=False), encoding="utf-8")
    evidence = json.loads(get(base + "/report"))
    (out / "evidence_report.json").write_text(json.dumps(evidence, indent=1, ensure_ascii=False), encoding="utf-8")
    wr = json.loads(get(base + "/written-report"))
    (out / "written_report.md").write_text(wr["markdown"], encoding="utf-8")
    rep = wr["report"]
    (out / "written_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")

    L: list = []
    q = session["question"]
    L += [f"# Run {args.run[:8]}: facts for a presentation", "", f"**Question:** {q}", ""]
    if events:
        done = next((e for e in events if e["event"] == "run_completed"), None)
        d = (done or {}).get("data") or {}
        total = secs(events[0]["timestamp"], events[-1]["timestamp"])
        L += ["## The run", "", f"- Total time: {total // 60} min {total % 60} s (from the first to the last event)",
              f"- Groq: {d.get('groqTokens', 0):,} tokens in {d.get('groqCalls', 0)} calls; rate limits hit {d.get('groqRateLimits', 0)} times, {d.get('groqParkedSeconds', 0):,} s of waiting summed over keys (7 free keys)", ""]
        L += ["## Stages", "", "| Stage | Time | What it produced |", "|---|---|---|"]
        for st, name in (("planner", "1 Planner"), ("retrieval", "2 Retrieval"), ("summarizer", "3 Evidence digest and judging"), ("factcheck", "4 Fact check"), ("report", "5 Written report")):
            s = next((e for e in events if e["event"] == "stage_started" and e.get("stage") == st), None)
            c = next((e for e in events if e["event"] == "stage_completed" and e.get("stage") == st), None)
            if s and c:
                t = secs(s["timestamp"], c["timestamp"])
                L.append(f"| {name} | {t // 60} min {t % 60} s | {c['message']} |")
        L.append("")
        steps = [e for e in events if e["event"] == "step" and e.get("data")]

        def last(lane, step, key):
            for e in reversed(steps):
                dd = e["data"]
                if dd.get("lane") == lane and dd.get("step") == step and key in dd:
                    return dd[key]
            return None

        L += ["## The funnel", "",
              f"- Search queries planned: {next((e['data'].get('queries') for e in events if e['event'] == 'stage_completed' and e.get('stage') == 'planner'), '?')}; candidate papers found: {last('papers', 'search', 'candidates')}; web sources found: {last('web', 'search', 'found')}",
              f"- Papers kept by the relevance judge: {last('papers', 'citations', 'kept')}; parsed to full text: {last('papers', 'parsing', 'usable')} of {last('papers', 'parsing', 'target')}",
              f"- Sources read by the digest model: {last('summarizer', 'digest', 'total')}; digests stored: {last('summarizer', 'store', 'stored')}",
              f"- Findings with a verified quote: {evidence['totals'].get('findingsQuoteFound')} of {evidence['totals'].get('findings')}",
              f"- Claims checked in Stage 4: {evidence['totals']['factChecked']}", ""]
    L += ["## The plan (sub-questions)", ""]
    for i, sq in enumerate(evidence["subQuestions"], 1):
        cov = sq.get("coverage") or {}
        fc = (sq.get("factCheck") or {}).get("counts") or {}
        L.append(f"{i}. {sq['topic']} (sources {len(sq.get('sources') or [])}, evidence sufficient: {cov.get('sufficient')}, claims: {fc})")
    L += ["", "## What the written report says", "", f"Status: {wr['status']}, template {wr['templateVersion']}, model {wr['model']}. Counts: {rep['overview']['counts']}", "", "### The answer", ""]

    def lab(x):
        return {"partly": " (partly supported)", "single": " (one source, not confirmed)"}.get(x["tier"], "")
    for x in rep["overview"]["summary"]:
        L.append(f"- {x['text']}{lab(x)}" + (f" [{', '.join(map(str, x['refs']))}]" if x["refs"] else ""))
    L += ["", "### The conclusion", ""]
    for x in rep["conclusion"]:
        L.append(f"- {x['text']}{lab(x)}" + (f" [{', '.join(map(str, x['refs']))}]" if x["refs"] else ""))
    L += ["", "### Limits the report states about itself", ""] + [f"- {l}" for l in rep["limitations"]]

    # one traced example: a partly supported sentence -> claim -> quote -> source
    claims = {}
    for sq in evidence["subQuestions"]:
        for c in (sq.get("factCheck") or {}).get("claims") or []:
            claims[c["claim"].strip().lower()] = c
    def toks(x):
        return {w for w in re.findall(r"[a-z][a-z\-]{3,}", x.lower())}

    example = None
    best = 0.0
    for sec in rep["sections"]:
        for s in sec["sentences"]:
            if s["tier"] != "partly" or s["origin"] != "llm" or len(s["claimIds"]) != 1:
                continue
            ts = toks(s["text"])
            for c in claims.values():
                tc = toks(c["claim"])
                j = len(ts & tc) / max(1, len(ts | tc))
                if j > best and c["label"] == "partially_supported" and any(e.get("relation") == "near_match" for e in c.get("evidence", [])):
                    best, example = j, (sec, s, c)
    if example and best >= 0.3:
        sec, s, c = example
        refs = {r["number"]: r for r in rep["references"]}
        L += ["", "## One sentence traced back to its sources", "", f"Section: *{sec['title']}*", "", f"> {s['text']}  *(partly supported)*", "",
              f"Citation numbers {s['refs']} point to:", ""]
        for n in s["refs"]:
            r = refs.get(n)
            if r:
                L.append(f"- [{n}] {r['text']}" + (f" ({r['url']})" if r.get("url") and r["url"] not in r["text"] else ""))
        L += ["", f"The Stage 4 claim behind it (Stage 5 claim id {s['claimIds'][0]}): \"{c['claim']}\"", f"Label: {LABELS.get(c['label'], c['label'])}; documents stating it: {c['supportDocCount']}; confidence {c['confidence']}", "", "Verbatim quotes kept for it:"]
        for e in [e for e in c.get("evidence", []) if e.get("relation") in ("supports", "near_match")][:3]:
            kind = "states it" if e["relation"] == "supports" else "close variant in another document"
            L.append(f"- {kind}: \"{e['quote'][:300]}\" ({e['sourceTitle']}; evidence level {e.get('evidenceLevel')})")
    dis = [(sec["title"], d) for sec in rep["sections"] for d in sec["disagreements"]]
    if dis:
        title, d = dis[0]
        L += ["", "## A disagreement the report shows instead of choosing a side", "", f"Section: *{title}*", "", d["note"], "",
              f"- Side A [{d['sideA']['ref']}] {d['sideA']['title']}: \"{d['sideA']['quote'][:320]}\"", f"- Side B [{d['sideB']['ref']}] {d['sideB']['title']}: \"{d['sideB']['quote'][:320]}\""]
    L += ["", "## Files in this folder", "", "- `written_report.md` / `written_report.json`: the written report (Stage 5)", "- `evidence_report.json`: every source, finding, claim, label and quote",
          "- `events.json` / `events_raw.txt`: the live events of the run (timeline, counts, tokens)", "- `session.json`: status and stage states", ""]
    (out / "README_facts.md").write_text("\n".join(L), encoding="utf-8")
    print(f"written to {out}: {len(L)} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
