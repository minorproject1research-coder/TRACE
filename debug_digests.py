import sys
sys.path.insert(0, '.')

from apps.api.services.db_service import supabase

qid = '6e735eb6-4b79-4c7e-af41-c88adaeee8fe'
digests = supabase.table('digests').select('*').eq('query_id', qid).eq('sub_question_id', '763a1e90').execute().data
for d in digests:
    print('Source:', d['source_id'])
    for f in d.get('findings', []):
        claim = f.get('claim', '')
        print('  Claim:', claim[:80] if claim else 'NONE')
        print('  answers_details:', f.get('answers_details'))
        print('  verified:', f.get('verified'))