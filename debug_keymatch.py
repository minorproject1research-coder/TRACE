import sys
sys.path.insert(0, '.')

from apps.api.services.db_service import supabase, get_papers_for_stage3, get_web_sources_for_stage3
from apps.api.agents.stage3_summarizer import chunk_selector, digest_generator, evidence_judge
from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
import hashlib

qid = '6e735eb6-4b79-4c7e-af41-c88adaeee8fe'
sq = supabase.table('sub_questions').select('*').eq('query_id', qid).eq('id', '763a1e90').execute().data[0]

cleaned_topic = _clean_topic(sq['main_topic'])
aspects, aspect_to_detail = flatten_aspects(sq['detail_questions'], sq['id'], cleaned_topic)

# Build jobs like the orchestrator (simplified)
jobs = []
papers = get_papers_for_stage3(qid, sq['id'])[:3]
for p in papers:
    chunks = chunk_selector.build_chunks(p)
    selected = chunk_selector.select_chunks(sq['main_topic'], chunks, detail_questions=aspects, main_topic=cleaned_topic)
    level = "full_text" if p.get("has_full_text") else "abstract"
    jobs.append({
        "source_type": "paper",
        "source": p,
        "selected": selected,
        "weight": p.get("combined_score"),
        "evidence_level": level,
    })

web_sources = get_web_sources_for_stage3(sq['id'])[:2]
for w in web_sources:
    snippet = w.get("snippet") or ""
    if len(snippet) >= 200:
        jobs.append({
            "source_type": "web",
            "source": w,
            "selected": [(0, snippet)],
            "weight": w.get("reliability_score"),
            "evidence_level": "web_snippet",
        })

# Generate digests
from apps.api.agents.stage3_summarizer import digest_generator
findings_per_job = []
for job in jobs:
    selected = job["selected"]
    if not selected:
        findings_per_job.append([])
        continue
    findings = digest_generator.generate_digest(
        sq['main_topic'],
        selected,
        detail_aspects=aspects,
        main_topic=cleaned_topic,
    )
    findings_per_job.append(findings)

# Build rows like the orchestrator
def _row(query_id, sq_id, source_type, src, findings, weight, evidence_level):
    return {
        "query_id": query_id,
        "sub_question_id": sq_id,
        "source_type": source_type,
        "source_id": str(src["id"]),
        "source_title": src.get("title"),
        "findings": findings,
        "verified_count": sum(1 for f in findings if f["verified"]),
        "total_count": len(findings),
        "weight": weight,
        "evidence_level": evidence_level,
    }

rows = []
for job, findings in zip(jobs, findings_per_job):
    rows.append(_row(qid, sq['id'], job["source_type"], job["source"], findings, job["weight"], job["evidence_level"]))

# Build chunk_lookup
chunk_lookup = {}
for job in jobs:
    for chunk_id, chunk_text in job["selected"]:
        chunk_lookup[str(chunk_id)] = chunk_text

# Now run the judge pipeline and trace the keys
print("=== Running judge pipeline with key tracing ===")

# Step 1: select_candidates
candidates = evidence_judge.select_candidates(aspects, rows, chunk_lookup)
print(f"\nCandidates generated: {len(candidates)}")
for c in candidates:
    claim_hash = hashlib.sha256(c["claim"].encode()).hexdigest()[:16]
    key = (c["aspect_idx"], c["source_id"], claim_hash)
    print(f"  Candidate: aspect_idx={c['aspect_idx']}, source_id={c['source_id']}, claim_hash={claim_hash}, key={key}")

# Step 2: build_judge_items
items = evidence_judge.build_judge_items(candidates, chunk_lookup)
print(f"\nItems built: {len(items)}")
for item in items:
    print(f"  Item ID: {item['id']}")

# Step 3: judge_candidates - let's trace the key parsing
print("\n=== Parsing item IDs ===")
for item in items:
    id_str = item["id"]
    if id_str.startswith("a") and "_s" in id_str and "_f" in id_str:
        aspect_idx_str = id_str[1:id_str.index("_s")]
        aspect_idx = int(aspect_idx_str)
        s_start = id_str.index("_s") + 2
        f_start = id_str.index("_f", s_start)
        source_id = id_str[s_start:f_start]
        claim_hash = hashlib.sha256(item["claim"].encode()).hexdigest()[:16]
        print(f"  Item: {item['id']}")
        print(f"    Parsed: aspect_idx={aspect_idx}, source_id={source_id}, claim_hash={claim_hash}")
        # Skip printing claim due to encoding issues

# Now let's check what the verdict keys would be
print("\n=== Expected verdict keys from candidates ===")
expected_keys = set()
for c in candidates:
    claim_hash = hashlib.sha256(c["claim"].encode()).hexdigest()[:16]
    expected_keys.add((c["aspect_idx"], c["source_id"], claim_hash))
print(f"Expected keys: {len(expected_keys)}")
for k in sorted(expected_keys):
    print(f"  {k}")

# Now let's see what the judge actually returns
from unittest.mock import patch
import httpx

original_call_judge_batch = evidence_judge._call_judge_batch

def traced_call_judge_batch(items, judge_url, api_key, timeout):
    print(f"\n=== Calling judge with {len(items)} items ===")
    for item in items:
        print(f"  Item: {item['id']}")
    result = original_call_judge_batch(items, judge_url, api_key, timeout)
    print(f"  Results: {len(result)} items")
    for r in result:
        print(f"  Result: id={r.get('id')}, verdict={r.get('verdict')}")
    return result

with patch('apps.api.agents.stage3_summarizer.evidence_judge._call_judge_batch', traced_call_judge_batch):
    candidates2, verdicts = evidence_judge.run_judge_for_subquestion(aspects, rows, chunk_lookup)
    print(f"\n=== Verdicts returned: {len(verdicts)} ===")
    for k, v in verdicts.items():
        print(f"  Verdict key: {k}")
        print(f"    Verdict: {v.get('verdict')}")

# Check which candidate keys match verdict keys
print("\n=== Key matching ===")
matched = 0
for exp_key in expected_keys:
    if exp_key in verdicts:
        matched += 1
        print(f"  MATCHED: {exp_key}")
    else:
        print(f"  MISSING: {exp_key}")
print(f"Matched: {matched}/{len(expected_keys)}")