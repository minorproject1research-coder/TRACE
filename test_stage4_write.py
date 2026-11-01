from types import SimpleNamespace
from apps.api.graph.nodes.factcheck_node import run_factcheck
from apps.api.services import db_service

QUERY_ID = "e4cb4c71-d1f0-4db3-88e1-c7c4831adee4"
sqs = [SimpleNamespace(id=i, main_topic="test") for i in ("3b44d9f9", "aa974cfe", "e85b7451")]

claims, summary = run_factcheck(QUERY_ID, sqs)
for k, v in summary.items():
    print(k, v)

for t in ("fact_claims", "contradictions"):
    n = db_service.supabase.table(t).select("*", count="exact").eq("query_id", QUERY_ID).execute().count
    print(t, "rows in DB:", n)