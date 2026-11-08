"""How much Groq did this project use? Reads logs/groq_usage.jsonl (written by apps/api/services/groq_pool.py for every call).

  python scripts/groq_usage.py [--hours 24] [--daily-limit 200000]

Shows tokens and calls per key, per purpose (digest, digest_loop2, stage4_judge, aspect_split ...), 429 counts, and the limits Groq reported in its
response headers (requests per day, tokens per minute) with what was left at the last call. Groq does NOT report the daily TOKEN limit in headers;
--daily-limit (default 200000, the free-tier figure published for openai/gpt-oss-120b; check your console) is only used for the "% of the day" column,
and counts only what THIS project sent in the window (other tools on the same accounts use the same limit).
"""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--daily-limit", type=int, default=200000)
    ap.add_argument("--file", default=str(ROOT / "logs" / "groq_usage.jsonl"))
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        print("no usage log yet:", path)
        return 0
    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            if datetime.fromisoformat(r["ts"]) >= since:
                rows.append(r)
        except (ValueError, KeyError):
            continue
    calls = [r for r in rows if "event" not in r]
    limited = [r for r in rows if r.get("event") == "429"]
    print(f"last {args.hours:g} hours: {len(calls)} calls, {sum(r['total'] for r in calls):,} tokens "
          f"({sum(r['prompt'] for r in calls):,} prompt + {sum(r['completion'] for r in calls):,} completion, of which {sum(r['reasoning'] for r in calls):,} reasoning), "
          f"{len(limited)} rate-limit answers (429)\n")

    by_key = defaultdict(Counter)
    for r in calls:
        by_key[r["key"]]["calls"] += 1
        by_key[r["key"]]["tokens"] += r["total"]
    for r in limited:
        by_key[r["key"]]["429"] += 1
    print(f"{'key':<6}{'calls':>7}{'tokens':>11}{'% of ' + str(args.daily_limit):>14}{'429s':>7}")
    for k, c in sorted(by_key.items()):
        print(f"...{k:<3}{c['calls']:>7}{c['tokens']:>11,}{100 * c['tokens'] / args.daily_limit:>13.0f}%{c['429']:>7}")
    print(f"      {'all':<3}{sum(c['calls'] for c in by_key.values()):>7}{sum(c['tokens'] for c in by_key.values()):>11,}"
          f"{100 * sum(c['tokens'] for c in by_key.values()) / (args.daily_limit * max(1, len(by_key))):>13.0f}%{sum(c['429'] for c in by_key.values()):>7}")

    by_purpose = defaultdict(Counter)
    for r in calls:
        by_purpose[r["purpose"]]["calls"] += 1
        by_purpose[r["purpose"]]["tokens"] += r["total"]
        by_purpose[r["purpose"]]["completion"] += r["completion"]
    print(f"\n{'purpose':<18}{'calls':>7}{'tokens':>11}{'tokens/call':>13}")
    for p, c in sorted(by_purpose.items(), key=lambda kv: -kv[1]["tokens"]):
        print(f"{p:<18}{c['calls']:>7}{c['tokens']:>11,}{c['tokens'] / c['calls']:>13,.0f}")

    last = {}
    for r in calls:
        if "rl_limit_requests" in r:
            last[r["key"]] = r
    if last:
        print("\nlimits Groq reported at each key's last call:")
        for k, r in sorted(last.items()):
            print(f"  ...{k}: requests per day {r.get('rl_limit_requests')} (left {r.get('rl_remaining_requests')}, resets in {r.get('rl_reset_requests')}); "
                  f"tokens per minute {r.get('rl_limit_tokens')} (left {r.get('rl_remaining_tokens')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
