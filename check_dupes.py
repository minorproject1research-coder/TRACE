from apps.api.services import db_service

digests = db_service.get_digests_for_stage4("df9582a9-bf28-4869-9197-96de932feb1b", "f3406beb")
print("rows:", len(digests), "| distinct source_id:", len({str(d["source_id"]) for d in digests}))