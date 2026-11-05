"""Offline experiment: how many unverified digest findings can be repaired by snapping the edited quote to the real passage?

The digest model is told to copy quotes word for word but edits them (drops citation markers, joins two sentences). quote_verifier then
marks the finding unverified and it is left out of judging and coverage. This script takes every unverified finding in the database whose
source text is stored, finds the best-aligned passage in that text, and writes the candidates (score, original quote, snapped passage,
claim) to reports/quote_snap_candidates.json for labeling. No LLM call, no Groq.

Pre-registered rule (2026-11-05, before looking at any score band): a score band is adopted for snapping only if, in a labeled sample of
at least 10 findings from that band, at least 90% of the snapped passages directly support the claim. Labels are assigned by me (an LLM).

Usage:  python tests/quote_snap_experiment.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from rapidfuzz import fuzz  # noqa: E402

from apps.api.agents.stage3_summarizer.quote_verifier import _norm  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402

CITATION = re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")


def clean(text: str) -> str:
    text = CITATION.sub("", text).replace("‑", "-").replace("‐", "-")
    text = re.sub(r"\(\s+", "(", text)
    return re.sub(r"\s+\)", ")", text)


def paragraphs(text: str, size: int = 700, step: int = 350) -> list[str]:
    """Overlapping windows of ~700 characters (a quote is at most 40 words), so one alignment search stays fast."""
    text = re.sub(r"\s+", " ", clean(text))
    return [text[i:i + size] for i in range(0, max(len(text) - size, 0) + step, step)] or [text]


def best_passage(quote: str, text: str):
    q = _norm(clean(quote))
    if len(q) < 20:
        return 0.0, None, ""
    best_score, best_win = 0.0, ""
    for win in paragraphs(text):
        s = fuzz.partial_ratio(q, _norm(win))
        if s > best_score:
            best_score, best_win = s, win
    if not best_win:
        return 0.0, None, ""
    al = fuzz.partial_ratio_alignment(q, _norm(best_win))
    passage = best_win[max(al.dest_start - 40, 0):al.dest_end + 40].strip()       # the aligned span plus a little context
    return best_score, al, passage


def fetch_all(table: str, columns: str, page: int = 500):
    rows, start = [], 0
    while True:
        chunk = supabase.table(table).select(columns).range(start, start + page - 1).execute().data
        rows += chunk
        if len(chunk) < page:
            return rows
        start += page


def main():
    digests = fetch_all("digests", "id,query_id,sub_question_id,source_type,source_id,source_title,findings")
    print(len(digests), "digests in the database")
    paper_ids = {d["source_id"] for d in digests if d["source_type"] == "paper"}
    texts = {}
    ids = list(paper_ids)
    for i in range(0, len(ids), 40):
        for r in supabase.table("parsed_papers").select("retrieved_paper_id,full_text").in_("retrieved_paper_id", ids[i:i + 40]).execute().data:
            texts[r["retrieved_paper_id"]] = r["full_text"] or ""
    web_ids = list({d["source_id"] for d in digests if d["source_type"] != "paper"})
    for i in range(0, len(web_ids), 40):
        for r in supabase.table("web_sources").select("id,snippet,title").in_("id", web_ids[i:i + 40]).execute().data:
            texts[r["id"]] = f"{r.get('title') or ''}. {r.get('snippet') or ''}"
    total = verified = no_text = 0
    cands = []
    for d in digests:
        f_list = d["findings"] if isinstance(d["findings"], list) else json.loads(d["findings"] or "[]")
        for f in f_list:
            total += 1
            if f.get("verified"):
                verified += 1
                continue
            text = texts.get(d["source_id"], "")
            if len(text) < 200:
                no_text += 1
                continue
            score, al, passage = best_passage(f.get("quote") or "", text)
            if not al:
                continue
            cands.append({"snapped": passage, "query_id": d["query_id"], "source_type": d["source_type"], "source_title": d["source_title"],
                          "score": round(score, 1), "claim": f.get("claim"), "quote": f.get("quote"), "digest_id": d["id"],
                          "_al": [al.src_start, al.src_end, al.dest_start, al.dest_end]})
    print(f"findings {total}: verified {verified}, unverified {total - verified} (no stored source text: {no_text}); candidates {len(cands)}")
    bands = [(90, 101), (80, 90), (70, 80), (60, 70), (0, 60)]
    for lo, hi in bands:
        n = sum(1 for c in cands if lo <= c["score"] < hi)
        print(f"  score {lo}-{min(hi, 100)}: {n}")
    for c in cands:
        c.pop("_al")
    (ROOT / "reports" / "quote_snap_candidates.json").write_text(json.dumps(cands, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
