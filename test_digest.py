import logging
logging.basicConfig(level=logging.INFO)

from apps.api.services.db_service import supabase
from apps.api.agents.stage3_summarizer.chunk_selector import build_chunks, select_chunks
from apps.api.agents.stage3_summarizer.digest_generator import generate_digest

row = supabase.table("parsed_papers").select("title,sections,full_text").limit(1).execute().data[0]
question = "Effect of RAG on hallucination rates"

selected = select_chunks(question, build_chunks(row))
findings = generate_digest(question, selected)

print("\ntitle:", row["title"][:70])
print("findings:", len(findings), "| verified:", sum(f["verified"] for f in findings))
for f in findings:
    print(f"\n[{'OK ' if f['verified'] else 'BAD'}] ({f['stance']}) {f['claim']}")
    print("   quote:", f["quote"][:160])