import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_url = os.environ["SUPABASE_URL"]
_key = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(_url, _key)


def write_task_plan(plan) -> None:
    sub_q_rows, query_rows = plan.to_supabase_rows()

    supabase.table("research_queries").upsert({
        "id": plan.query_id,
        "raw_query": plan.raw_query,
    }).execute()

    if sub_q_rows:
        supabase.table("sub_questions").upsert(sub_q_rows).execute()

    if query_rows:
        supabase.table("queries").insert(query_rows).execute()