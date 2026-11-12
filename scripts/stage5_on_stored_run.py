"""Write the Stage 5 report of a STORED run (no new retrieval, no Stage 3 or 4 work) and print what it contains.

  venv/Scripts/python.exe scripts/stage5_on_stored_run.py --run <query_id> [--out PATH] [--dry]

Reads the stored claims, contradictions, coverage and sources of the run (loader.load_inputs), builds the report (assembler.build_report), prints the
status, the tier counts, the per-section counts and the token use, and writes PATH.md (Markdown) and PATH.json (structured report + stats).
--out is a base path (a .md or .json suffix is ignored) or a folder; the default is reports/stage5/<run> (the folder is created; do not commit it).

  --dry   no language model and no NLI model: every sentence is the deterministic template sentence and the summary is the extractive template.
          It costs no Groq tokens and loads nothing; use it to look at the structure and the tiers of a run before spending tokens.

Without --dry the real model is used (STAGE5_MODEL through the Groq pool, about 50k tokens for 12 calls: an estimate, see docs/STAGE5.md) and the
sentence checks load the NLI model of Stage 4. Nothing is written to the database by this script.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DIR = Path("reports") / "stage5"


def output_base(out, run: str) -> Path:
    """The base path (without suffix) of the two output files."""
    if not out:
        return DEFAULT_DIR / run
    p = Path(out)
    if p.suffix.lower() in (".md", ".json"):
        return p.with_suffix("")
    if p.is_dir() or str(out).endswith(("/", "\\")):
        return p / run
    return p


def print_summary(result: dict, run: str, write=print) -> None:
    report, stats = result["report"], result["stats"]
    claims = stats.get("claims", {})
    write(f"run {run}: status {result['status']}  model {result['model']}  template {result['template_version']}")
    write(f"claims {claims.get('total', 0)}: supported {claims.get('supported', 0)}, partly {claims.get('partly', 0)}, single {claims.get('single', 0)}, "
          f"disputed {claims.get('disputed', 0)}, filtered {claims.get('filtered', 0)} {stats.get('filtered') or ''}")
    sent = stats.get("sentences", {})
    write(f"sentences written {stats.get('written', {})}: llm {sent.get('llm', 0)}, fallback {sent.get('fallback', 0)}, dropped {sent.get('dropped', 0)}, "
          f"template {sent.get('template', 0)}; references {stats.get('references', 0)}")
    write(f"calls {stats.get('calls', 0)}, tokens {stats.get('tokens', 0)} (prompt {stats.get('prompt_tokens', 0)}, completion {stats.get('completion_tokens', 0)}), "
          f"retried {stats.get('retried', 0)}, cache hits {stats.get('cache_hits', 0)}, nli pairs {stats.get('nli', {}).get('pairs', 0)}, "
          f"judge calls {stats.get('judge', {}).get('calls', 0)}, {stats.get('seconds', 0)} s")
    for i, sec in enumerate(report.get("sections", []), 1):
        c = sec.get("counts", {})
        write(f"  section {i}: {len(sec['sentences'])} sentences, {len(sec['disagreements'])} disagreements, {len(sec['gaps'])} gap lines "
              f"(claims {c.get('total', 0)}: supported {c.get('supported', 0)}, partly {c.get('partly', 0)}, single {c.get('single', 0)}, "
              f"disputed {c.get('disputed', 0)}, filtered {c.get('filtered', 0)})  {sec['title'][:70]}")
    for w in result.get("warnings", []):
        write(f"  warning: {w}")


def main(argv=None, *, load=None, build=None, write=print) -> int:
    """`load(query_id) -> inputs` and `build(inputs, **kw) -> result` are injectable (the tests pass fakes); the defaults are the real ones."""
    ap = argparse.ArgumentParser(description="Write the Stage 5 report of a stored run.")
    ap.add_argument("--run", required=True, help="the run id (research_queries.id)")
    ap.add_argument("--out", help="base path of the .md and .json files (default reports/stage5/<run>)")
    ap.add_argument("--dry", action="store_true", help="no language model and no NLI: deterministic template sentences only (costs nothing)")
    args = ap.parse_args(argv)
    if load is None:
        from apps.api.agents.stage5_report import loader
        load = loader.load_inputs
    if build is None:
        from apps.api.agents.stage5_report import assembler
        build = assembler.build_report
    inputs = load(args.run)
    if not (inputs.get("status_hints") or {}).get("found", True):
        write(f"run {args.run} was not found in the database")
        return 2
    result = build(inputs, deterministic=bool(args.dry))
    print_summary(result, args.run, write)
    base = output_base(args.out, args.run)
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{base}.md").write_text(result["markdown"], encoding="utf-8")
    payload = {k: result[k] for k in ("status", "report", "stats", "warnings", "model", "template_version")}
    Path(f"{base}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    write(f"written: {base}.md and {base}.json")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # the report has quotes with characters the Windows console cannot print
    except Exception:                                                   # noqa: BLE001
        pass
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    import logging

    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")      # the same file the app writes (apps/api/main.py): why sentences fell back
    _log = logging.getLogger("apps.api.agents.stage5_report")
    _log.setLevel(logging.INFO)
    (ROOT / "logs").mkdir(exist_ok=True)
    for _h in (logging.FileHandler(ROOT / "logs" / "stage5_report.log", encoding="utf-8"), logging.StreamHandler()):
        _h.setFormatter(_fmt)
        _log.addHandler(_h)
    raise SystemExit(main())
