#!/usr/bin/env python3
"""
Compare the current aspect-splitter prompt (OLD) with a variant that also splits separate dimensions / metrics (NEW) on every stored
compound detail question. Real LLM calls (Groq via the key pool); does NOT touch the aspect cache or the database.

Pre-registered decision rule (fixed before the first run):
  adopt NEW only if (a) at least 75% of the changes it makes are judged good splits (judged blind: the two lists are shown as A/B in random
  order), and (b) the share of details whose aspect list changes between OLD and NEW exceeds the OLD-versus-OLD share (sampling noise of the
  same prompt) by at least 10 percentage points.

  python tests/aspect_split_prompt_test.py run     # calls the model, writes reports/aspect_split_prompt_test.json
  python tests/aspect_split_prompt_test.py show    # prints the changed cases blind (A/B), no model calls
  python tests/aspect_split_prompt_test.py score judgments.json   # judgments: {"<case no>": "good"|"bad"|"neutral"}
"""
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic  # noqa: E402
from apps.api.agents.stage3_summarizer.detail_aspects import ASPECT_SPLIT_PROMPT as OLD_PROMPT  # noqa: E402
from apps.api.services.llm_service import squeezer_json  # noqa: E402

OUT = Path("reports/aspect_split_prompt_test.json")
NOISE_REPEATS = 40

NEW_PROMPT = """Split the following detail question into distinct aspects when it asks for two or more separate things that a source could answer on its own.

Detail question: {detail}

Subject/context: {topic}

Return ONLY JSON: {{"aspects": ["aspect 1", "aspect 2", ...]}}

Rules:
- Split when the question names two or more separate things to be answered individually. These can be separate kinds of information, or separate
  dimensions, criteria or metrics that would be measured or reported separately.
  Examples:
  - "advantages and disadvantages of X" -> ["advantages of X", "disadvantages of X"]
  - "examples and benefits of X" -> ["examples of X", "benefits of X"]
  - "how X is defined and measured" -> ["how X is defined", "how X is measured"]
  - "risks and benefits" -> ["risks of X", "benefits of X"]
  - "causes and effects" -> ["causes of X", "effects of X"]
  - "how X compares with Y in training efficiency and long-sequence performance" -> ["how X compares with Y in training efficiency", "how X compares with Y in long-sequence performance"]
  - "impact on speed and memory" -> ["impact on speed", "impact on memory"]
- Do NOT split when "and" or "or" joins parts of ONE concept or noun phrase, or near-synonyms:
  - "LoRA and full fine-tuning" -> ["LoRA and full fine-tuning"] (the two things being compared are one subject)
  - "encoder-decoder architecture" -> ["encoder-decoder architecture"] (one concept)
  - "e.g. A, B, C" -> ["e.g. A, B, C"] (examples list)
  - "definition and properties" -> ["definition and properties"] (one concept with two words)
  - "empirical results and findings" -> ["empirical results and findings"] (near-synonyms)
- Each aspect must be a self-contained question that includes the subject and, for a comparison, both things being compared.
- Maximum 3 aspects.
- If no clear split, return the original as a single aspect.
"""

COMPOUND = re.compile(r"\b(and|or|versus|vs\.?|compared?|between)\b|,|/", re.I)


def split(prompt_template: str, detail: str, topic: str):
    try:
        data = squeezer_json(prompt_template.format(detail=detail, topic=topic))
        aspects = data.get("aspects", [])
        if not isinstance(aspects, list) or not (1 <= len(aspects) <= 3) or not all(isinstance(a, str) and a.strip() for a in aspects):
            return [detail]
        return [a.strip() for a in aspects]
    except Exception as e:                       # a failed call is recorded, never silently turned into "no split"
        return {"error": str(e)[:120]}


def run():
    from apps.api.services.db_service import supabase
    details = {}
    for sq in supabase.table("sub_questions").select("main_topic,detail_questions").execute().data:
        for d in sq["detail_questions"]:
            details.setdefault(d.strip(), _clean_topic(sq["main_topic"]))
    cases = [(d, t) for d, t in details.items() if COMPOUND.search(d)]
    print(f"{len(cases)} compound detail questions; calls: {2 * len(cases) + NOISE_REPEATS}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        old = list(pool.map(lambda c: split(OLD_PROMPT, *c), cases))
        new = list(pool.map(lambda c: split(NEW_PROMPT, *c), cases))
        noise_cases = cases[:NOISE_REPEATS]
        old2 = list(pool.map(lambda c: split(OLD_PROMPT, *c), noise_cases))
    OUT.write_text(json.dumps({"cases": [{"detail": d, "topic": t, "old": o, "new": n} for (d, t), o, n in zip(cases, old, new)],
                               "noise": [{"detail": c[0], "old": o, "old2": o2} for c, o, o2 in zip(noise_cases, old, old2)]},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    report()


def _norm(a):
    return None if isinstance(a, dict) else [re.sub(r"\W+", " ", x.lower()).strip() for x in a]


def report():
    d = json.loads(OUT.read_text(encoding="utf-8"))
    ok = [c for c in d["cases"] if not isinstance(c["old"], dict) and not isinstance(c["new"], dict)]
    changed = [c for c in ok if len(c["old"]) != len(c["new"])]
    differ_text = [c for c in ok if _norm(c["old"]) != _norm(c["new"])]
    nz = [n for n in d["noise"] if not isinstance(n["old"], dict) and not isinstance(n["old2"], dict)]
    nz_changed = [n for n in nz if len(n["old"]) != len(n["old2"])]
    nz_text = [n for n in nz if _norm(n["old"]) != _norm(n["old2"])]
    count = lambda cs, k: tuple(sum(1 for c in cs if len(c[k]) == n) for n in (1, 2, 3))
    print(f"\nusable cases {len(ok)} of {len(d['cases'])} (errors: {len(d['cases']) - len(ok)})")
    print(f"number of aspects per detail (1 / 2 / 3):  OLD {count(ok, 'old')}  NEW {count(ok, 'new')}")
    print(f"aspect COUNT differs OLD vs NEW: {len(changed)}/{len(ok)} = {100 * len(changed) / max(len(ok), 1):.0f}%   | wording differs: {len(differ_text)}/{len(ok)}")
    print(f"noise: OLD vs OLD (same prompt twice) aspect COUNT differs: {len(nz_changed)}/{len(nz)} = {100 * len(nz_changed) / max(len(nz), 1):.0f}%   | wording differs: {len(nz_text)}/{len(nz)}")
    print(f"NEW splits more: {sum(1 for c in changed if len(c['new']) > len(c['old']))}, NEW splits less: {sum(1 for c in changed if len(c['new']) < len(c['old']))}")


def show():
    d = json.loads(OUT.read_text(encoding="utf-8"))
    rng = random.Random(11)
    changed = [c for c in d["cases"] if not isinstance(c["old"], dict) and not isinstance(c["new"], dict) and len(c["old"]) != len(c["new"])]
    key = {}
    for i, c in enumerate(changed, 1):
        flip = rng.random() < 0.5
        a, b = (c["new"], c["old"]) if flip else (c["old"], c["new"])
        key[str(i)] = "A=new" if flip else "A=old"
        print(f"\n#{i}  DETAIL: {c['detail']}\n   A: {a}\n   B: {b}")
    Path("reports/aspect_split_prompt_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")


def score(path):
    key = json.loads(Path("reports/aspect_split_prompt_key.json").read_text(encoding="utf-8"))
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    # j[case] = "A" or "B" (the better list) or "tie"; translate to new/old
    wins = {"new": 0, "old": 0, "tie": 0}
    for case, pick in j.items():
        if pick == "tie":
            wins["tie"] += 1
        else:
            wins["new" if (pick == "A") == (key[case] == "A=new") else "old"] += 1
    n = sum(wins.values())
    print("judgments:", wins, f"-> NEW preferred in {100 * wins['new'] / max(n, 1):.0f}% of {n} changed cases (rule: >= 75% good)")


if __name__ == "__main__":
    {"run": run, "show": show, "report": report}.get(sys.argv[1], lambda: score(sys.argv[2]))()
