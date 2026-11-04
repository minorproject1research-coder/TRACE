import sys
import logging
from types import SimpleNamespace
logging.basicConfig(level=logging.INFO)

from apps.api.services.db_service import supabase
from apps.api.graph.nodes.factcheck_node import run_factcheck

# python test_stage4.py      -> latest query;  python test_stage4.py 1 -> the one before
offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
queries = (supabase.table("research_queries").select("id,raw_query")
           .order("created_at", desc=True).limit(offset + 1).execute().data)
if len(queries) <= offset:
    print("No such query.")
    sys.exit(1)

q = queries[offset]
sqs = supabase.table("sub_questions").select("id,main_topic").eq("query_id", q["id"]).execute().data
print("query:", q["raw_query"], "| sub-questions:", len(sqs))
for s in sqs:
    n = len(supabase.table("digests").select("id").eq("sub_question_id", s["id"]).execute().data)
    print(f"  {s['id']}: {n} digest rows")

claims, summary = run_factcheck(q["id"], [SimpleNamespace(**s) for s in sqs])

print()
for sq_id, s in summary.items():
    print(sq_id, s)

print()
for r in claims:
    print(f"[{r['label'].upper():12}] conf={r['confidence']:.2f}  docs +{r['support_doc_count']}/-{r['contra_doc_count']}"
          f"{'  CONTESTED' if r['contested'] else ''}\n   {r['claim']}")