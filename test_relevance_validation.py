from apps.api.services.db_service import supabase

result = supabase.table("retrieved_papers") \
    .select("title, abstract, relevance_score, sub_question_id") \
    .not_.is_("relevance_score", "null") \
    .order("relevance_score", desc=True) \
    .limit(60) \
    .execute()

papers = result.data

print(f"Total papers fetched: {len(papers)}\n")
print("=" * 80)

for i, p in enumerate(papers, 1):
    print(f"\n[{i}] Score: {p['relevance_score']:.3f}  |  Sub-question: {p['sub_question_id']}")
    print(f"Title: {p['title']}")
    print(f"Abstract: {(p['abstract'] or '')[:200]}...")
    print("-" * 80)