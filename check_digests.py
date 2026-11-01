from apps.api.services import db_service

digests = db_service.get_digests_for_stage4("df9582a9-bf28-4869-9197-96de932feb1b", "f3406beb")
print("columns:", list(digests[0].keys()))

for d in digests:
    fs = d.get("findings")
    print("\n", d.get("source_title", "")[:60], "| type:", type(fs).__name__,
          "| n:", len(fs) if fs else 0, "| level:", d.get("evidence_level"), "| rel:", d.get("reliability"))
    for f in (fs or [])[:3]:
        if isinstance(f, dict):
            print("   verified:", f.get("verified"), "| grounded:", f.get("grounded"),
                  "| has claim:", bool(f.get("claim")), "| has quote:", bool(f.get("quote")))
        else:
            print("   finding is not a dict:", type(f).__name__, str(f)[:80])