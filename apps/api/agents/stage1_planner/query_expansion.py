import json
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

QUERY_EXPANSION_PROMPT = """You are a search query optimizer for a research assistant.

Given a research sub-question and its detail questions, generate 2-4 diverse
search-ready query variants. Variants should differ in phrasing, specificity,
and terminology so a search engine returns a wide, non-redundant set of results.

Sub-question: {main_topic}
Detail questions:
{detail_questions}

Return ONLY a JSON array of strings, nothing else. Example:
["query variant 1", "query variant 2", "query variant 3"]
"""


def expand(main_topic: str, detail_questions: list[str]) -> list[str]:
    prompt = QUERY_EXPANSION_PROMPT.format(
        main_topic=main_topic,
        detail_questions="\n".join(f"- {q}" for q in detail_questions),
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    raw = response.choices[0].message.content.strip()
    return _safe_parse(raw)[:4]


def _safe_parse(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json\n", "", 1)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(q).strip() for q in parsed if str(q).strip()]
    except json.JSONDecodeError:
        pass
    lines = [l.strip("-• ").strip() for l in text.splitlines() if l.strip()]
    return lines if lines else [raw]