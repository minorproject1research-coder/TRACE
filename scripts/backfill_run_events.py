"""Store the timeline of a finished run that ran BEFORE migration 017, from the events saved by scripts/export_run_bundle.py (events.json).

The run page draws its timeline from the stored events (table run_events). A run exported to a bundle folder has them in events.json (the same
events GET /api/research/{id}/events sent: seq, event, stage, status, message, data, timestamp) and its run id in session.json.

    python scripts/backfill_run_events.py reports/ppt_example reports/ppt_example_rerun            # dry run: checks the files and the table, writes nothing
    python scripts/backfill_run_events.py reports/ppt_example reports/ppt_example_rerun --write    # stores the events

A run that already has stored events is skipped (never overwritten). Writing is idempotent anyway: (query_id, seq) is the key.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.services import run_event_store  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402

CHUNK = 100


def load_bundle(folder: Path) -> tuple[str, list[dict]]:
    run_id = json.loads((folder / "session.json").read_text(encoding="utf-8"))["id"]
    events = json.loads((folder / "events.json").read_text(encoding="utf-8"))
    seqs = [e["seq"] for e in events]
    if not events or seqs != list(range(seqs[0], seqs[0] + len(seqs))):
        raise SystemExit(f"{folder}: the events are empty or their seq numbers have a gap; not storing a partial timeline")
    if events[-1]["event"] not in run_event_store.TERMINAL:
        raise SystemExit(f"{folder}: the events do not end with run_completed or run_failed; not storing an unfinished timeline")
    return run_id, events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+", type=Path, help="bundle folders (events.json and session.json inside)")
    ap.add_argument("--write", action="store_true", help="store the events (without it nothing is written)")
    args = ap.parse_args()

    for folder in args.folders:
        run_id, events = load_bundle(folder)
        stored = run_event_store.get_events(run_id)
        print(f"{folder}: run {run_id}, {len(events)} events ({events[0]['timestamp']} to {events[-1]['timestamp']}), already stored: {len(stored)}")
        if stored:
            print("   skipped: this run already has a stored timeline")
            continue
        if not args.write:
            print("   dry run: nothing written (add --write)")
            continue
        rows = [run_event_store.to_row(run_id, e) for e in events]
        for i in range(0, len(rows), CHUNK):
            supabase.table(run_event_store.TABLE).upsert(rows[i:i + CHUNK], on_conflict="query_id,seq").execute()
        back = run_event_store.get_events(run_id)
        same = back == [run_event_store.from_row(r) for r in rows]
        print(f"   stored {len(rows)} events; read back {len(back)}; identical to the file: {same}")
        if not same:
            raise SystemExit(f"{folder}: what was read back differs from what was written")


if __name__ == "__main__":
    main()
