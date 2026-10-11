"""Re-parse the stored Markdown of old parsed_papers rows with the current parser and stamp them with PARSER_VERSION.

Rows written before migration 009 have parser_version NULL and are ignored by the parse cache. Their full_text (the
Docling Markdown) is still in the table, so sections, references and abstract can be rebuilt WITHOUT downloading or
calling Docling again. Title, authors and abstract come from retrieved_papers (API metadata), as in a fresh parse.
Figures are kept as they are.

    python scripts/backfill_parsed_papers.py --dry-run     # report only
    python scripts/backfill_parsed_papers.py               # update the rows
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.agents.stage2_retrieval.markdown_parser import PARSER_VERSION, parse_markdown  # noqa: E402
from apps.api.agents.stage2_retrieval.paper_retrieval_agent import ParsedPaper, PaperRetrievalAgent  # noqa: E402
from apps.api.services import db_service  # noqa: E402

MIN_CHARS = 3000
PAGE = 50


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sb = db_service.supabase

    updated = skipped = 0
    while True:
        rows = (sb.table("parsed_papers")
                .select("id,retrieved_paper_id,full_text,figures")
                .is_("parser_version", "null").limit(PAGE).execute().data)
        if not rows:
            break
        progressed = False
        for row in rows:
            ft = row.get("full_text") or ""
            if len(ft) < MIN_CHARS:
                # nothing worth reusing; stamp it so the loop does not see it again (the cache ignores short rows)
                if not args.dry_run:
                    sb.table("parsed_papers").update({"parser_version": PARSER_VERSION}).eq("id", row["id"]).execute()
                skipped += 1
                progressed = True
                continue
            meta = db_service.get_retrieved_paper(row["retrieved_paper_id"]) or {}
            parsed = parse_markdown(ft)
            paper = ParsedPaper(
                retrieved_paper_id=row["retrieved_paper_id"], title=parsed.title, authors=parsed.authors,
                abstract=parsed.abstract, sections=[], references=parsed.references, figures=[], full_text=ft)
            PaperRetrievalAgent._apply_metadata(paper, meta)
            print(f"{'would update' if args.dry_run else 'update'}: {paper.title[:70]} | sections {len(parsed.sections)}"
                  f" | refs {len(parsed.references)} | {len(ft)} chars")
            if not args.dry_run:
                sb.table("parsed_papers").update({
                    "title": paper.title, "authors": paper.authors, "abstract": paper.abstract,
                    "sections": parsed.sections, "cited_references": parsed.references,
                    "parser_version": PARSER_VERSION,
                }).eq("id", row["id"]).execute()
            updated += 1
            progressed = True
        if args.dry_run or not progressed:
            break                                           # a dry run would otherwise loop on the same rows
    print(f"done: {updated} rows {'would be ' if args.dry_run else ''}updated, {skipped} short rows skipped")


if __name__ == "__main__":
    main()
