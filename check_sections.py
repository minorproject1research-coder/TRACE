from apps.api.services.db_service import supabase

rows = supabase.table("parsed_papers").select("sections").limit(3).execute().data
print("rows fetched:", len(rows))

for r in rows:
    secs = r["sections"] or []
    print("\nsections count:", len(secs))
    if secs:
        print("keys:", list(secs[0].keys()))
        print({k: str(v)[:80] for k, v in secs[0].items()})