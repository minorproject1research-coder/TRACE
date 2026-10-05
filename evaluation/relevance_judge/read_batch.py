"""Print candidate rows for hand-labeling: python -m evaluation.relevance_judge.read_batch sq01 sq02 ..."""
import sys
from pathlib import Path
from .common import ABSTRACT_CHAR_LIMIT, read_jsonl

rows = read_jsonl(Path(__file__).parent / "candidates.jsonl")
for sid in sys.argv[1:]:
    group = [r for r in rows if r["sub_question_id"] == sid]
    print(f"\n######## {sid}  SUB-QUESTION: {group[0]['sub_question']}\n")
    for r in group:
        print(f"[{r['id']}] ({r['year']}) {r['title']}\n{r['abstract'][:ABSTRACT_CHAR_LIMIT]}\n")
