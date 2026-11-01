import sys

from apps.api.services import db_service
from apps.api.agents.stage4_factcheck import fact_checker
from apps.api.agents.stage4_factcheck.contradiction_detector import detect


from collections import Counter

def list_runs():
    rows = db_service.supabase.table("digests").select("query_id, sub_question_id").limit(2000).execute().data
    counts = Counter((r["query_id"], r["sub_question_id"]) for r in rows)
    print("digests  command\n")
    for (q, s), n in sorted(counts.items(), key=lambda t: -t[1])[:15]:
        print(f"{n:>7}  python run_stage4_demo.py {q} {s}")


if len(sys.argv) != 3:
    list_runs()
    sys.exit(0)

query_id, sub_question_id = sys.argv[1], sys.argv[2]
digests = db_service.get_digests_for_stage4(query_id, sub_question_id)
print(f"digests: {len(digests)}")

claims = fact_checker.load_claims(digests)
print(f"claims loaded: {len(claims)}")

clusters = fact_checker.verify_support(fact_checker.build_clusters(claims))
print(f"clusters: {len(clusters)}")

conflicts, disagreements = detect(clusters)
rows = fact_checker.label_clusters(clusters, conflicts)

print("\n=== LABELS ===")
for r in sorted(rows, key=lambda r: r["label"]):
    print(f"{r['label']:<13} conf={r['confidence']:.2f} "
          f"sup_docs={r['support_doc_count']} con_docs={r['contra_doc_count']} | {r['claim']}")

print(f"\n=== DISAGREEMENTS ({len(disagreements)}) ===")
for d in disagreements:
    print(f"A: {d['claim_a']}\nB: {d['claim_b']}\nwhy: {d['reason']}\n")