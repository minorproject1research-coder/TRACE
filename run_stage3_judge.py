#!/usr/bin/env python3
"""
Run Stage 3 with judge for all 3 audit queries.
Usage: python run_stage3_judge.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()   # JUDGE_URL / JUDGE_API_KEY come from .env, never from source
os.environ['USE_JUDGE_COVERAGE'] = 'true'

from apps.api.services.db_service import supabase
from apps.api.graph.nodes.summarizer_node import summarizer_node
from apps.api.graph.state import SharedResearchState
from apps.api.models.task_plan import TaskPlan

query_ids = [
    '6e735eb6-4b79-4c7e-af41-c88adaeee8fe',
    '6e0ccec0-2109-4794-8063-f077c4eac548',
    '780ed8a5-8794-49df-97e2-4548bbe10aeb'
]

for qid in query_ids:
    print(f'=== Query {qid} ===')
    query = supabase.table('research_queries').select('*').eq('id', qid).execute().data[0]
    sub_questions = supabase.table('sub_questions').select('*').eq('query_id', qid).execute().data
    
    task_plan = TaskPlan(query_id=qid, raw_query=query['raw_query'], sub_questions=[])
    for sq in sub_questions:
        task_plan.sub_questions.append(type('obj', (object,), sq))
    
    state = SharedResearchState(raw_query=query['raw_query'], task_plan=task_plan)
    result = summarizer_node(state)
    
    for sq_id, cov in result.get('coverage', {}).items():
        ju = cov.get('judge_used')
        fr = cov.get('fallback_reason')
        df = cov.get('digest_failures')
        ua = cov.get('unjudged_aspects', [])
        uca = cov.get('uncovered_aspects', [])
        ur = cov.get('uncovered_reasons', {})
        js = cov.get('judge_stats', {})
        print(f'  {sq_id}: judge_used={cov.get("judge_used")}, fallback={fr}, digest_failures={df}')
        print(f'    judge_stats={js}')
        print(f'    unjudged_aspects={ua}')
        print(f'    uncovered_aspects={uca}')
        print(f'    uncovered_reasons={ur}')
        if cov.get('aspect_evidence'):
            print(f'    aspects:')
            for i, ev in cov.get('aspect_evidence', {}).items():
                print(f'      Aspect {i}: yes={len([e for e in ev if e.get("verdict")=="yes"])}, sources={len(set(e["source_id"] for e in ev))}, evidence={ev}')

print('\nDone.')