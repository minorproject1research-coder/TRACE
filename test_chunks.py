# test_chunks.py
from apps.api.services.db_service import supabase
from apps.api.agents.stage3_summarizer.chunk_selector import build_chunks, select_chunks

row = supabase.table("parsed_papers").select("title,sections,full_text").limit(1).execute().data[0]
chunks = build_chunks(row)
print("title:", row["title"][:70])
print("total chunks:", len(chunks))

for cid, text in select_chunks("Effect of RAG on hallucination rates", chunks):
    print(f"\n[chunk {cid}] {text[:150]}...")