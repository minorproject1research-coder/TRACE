import sys
sys.path.insert(0, '.')

from apps.api.services.db_service import supabase

qid = '6e735eb6-4b79-4c7e-af41-c88adaeee8fe'
digests = supabase.table('digests').select('*').eq('query_id', qid).eq('sub_question_id', '763a1e90').execute().data
with open('debug_output.txt', 'w', encoding='utf-8') as out:
    for d in digests:
        out.write('Source: ' + d['source_id'] + '\n')
        for f in d.get('findings', []):
            claim = f.get('claim', '')
            out.write('  Claim: ' + (claim[:80] if claim else 'NONE') + '\n')
            out.write('  answers_details: ' + str(f.get('answers_details')) + '\n')
            out.write('  verified: ' + str(f.get('verified')) + '\n')