from apps.api.services.db_service import supabase

res = supabase.table("research_queries").select("*").limit(1).execute()
print("Connection OK:", res)