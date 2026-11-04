from collections import defaultdict
from apps.api.services import db_service

rows, start = [], 0
while True:
    page = (db_service.supabase.table("digests")
            .select("query_id, sub_question_id, findings, verified_count, total_count")
            .range(start, start + 999).execute().data)
    rows += page
    if len(page) < 1000:
        break
    start += 1000

stats = defaultdict(lambda: [0, 0, 0])   # digests, findings, verified
for r in rows:
    k = (r["query_id"], r["sub_question_id"])
    stats[k][0] += 1
    stats[k][1] += len(r["findings"] or [])
    stats[k][2] += r["verified_count"] or 0

print(f"total digest rows: {len(rows)}\n")
print("digests findings verified  command")
for (q, s), (n, f, v) in sorted(stats.items(), key=lambda t: -t[1][2])[:15]:
    print(f"{n:>7} {f:>8} {v:>8}  python run_stage4_demo.py {q} {s}")
print("\nsub-questions with zero findings:", sum(1 for v in stats.values() if v[1] == 0), "of", len(stats))