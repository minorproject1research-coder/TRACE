import sys
import logging
logging.basicConfig(level=logging.INFO)

from apps.api.services.db_service import supabase
from apps.api.models.task_plan import TaskPlan, SubQuestion
from apps.api.graph.state import SharedResearchState
from apps.api.graph.nodes.summarizer_node import summarizer_node

# python test_stage3.py      -> latest query
# python test_stage3.py 1    -> second latest query, and so on
offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0

queries = (supabase.table("research_queries").select("id,raw_query")
           .order("created_at", desc=True).limit(offset + 1).execute().data)
if len(queries) <= offset:
    print("No such query in research_queries.")
    sys.exit(1)

q = queries[offset]
sqs = (supabase.table("sub_questions").select("id,main_topic,detail_questions")
       .eq("query_id", q["id"]).execute().data)

print("query:", q["raw_query"], "| sub-questions:", len(sqs))
for s in sqs:
    n_p = len(supabase.table("retrieved_papers").select("id").eq("sub_question_id", s["id"]).execute().data)
    n_w = len(supabase.table("web_sources").select("id").eq("sub_question_id", s["id"]).execute().data)
    print(f"  {s['id']}: {n_p} papers, {n_w} web sources available")

plan = TaskPlan(
    query_id=q["id"],
    raw_query=q["raw_query"],
    sub_questions=[SubQuestion(id=s["id"], main_topic=s["main_topic"],
                               detail_questions=s["detail_questions"]) for s in sqs],
)
result = summarizer_node(SharedResearchState(raw_query=q["raw_query"], task_plan=plan))

rows = result["digests"]
print("\ndigests:", len(rows),
      "| verified findings:", sum(r["verified_count"] for r in rows),
      "/", sum(r["total_count"] for r in rows))
for sq_id, cov in result["coverage"].items():
    print(sq_id, cov)