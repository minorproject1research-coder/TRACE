import os
import json
import httpx
from dotenv import load_dotenv

from apps.api.services import groq_pool

load_dotenv()

BACKEND = os.getenv("SQUEEZER_BACKEND", "groq")  # groq | ollama
GROQ_MODEL = os.getenv("SQUEEZER_GROQ_MODEL", "openai/gpt-oss-120b")
OLLAMA_MODEL = os.getenv("SQUEEZER_OLLAMA_MODEL", "qwen3.5:3b")  # verify with `ollama list`
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = OLLAMA_MODEL if BACKEND == "ollama" else GROQ_MODEL


def squeezer_json(prompt: str, *, temperature: float = 0.1, seed: int | None = None, purpose: str = "other") -> dict:
    """Sends the prompt to the configured Squeezer backend and parses a JSON reply. seed is best effort (Groq documents it as such)."""
    if BACKEND == "ollama":
        r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=180, json={
            "model": OLLAMA_MODEL, "stream": False, "format": "json",
            "options": {"temperature": temperature, **({"seed": seed} if seed is not None else {})},
            "messages": [{"role": "user", "content": prompt}],
        })
        r.raise_for_status()
        raw = r.json()["message"]["content"]
    else:
        for attempt in range(2):                    # a reply that is not valid JSON (cut off, stray text) gets one more try
            extra = {"seed": seed} if seed is not None else {}
            resp = groq_pool.chat(messages=[{"role": "user", "content": prompt}], model=GROQ_MODEL, temperature=temperature, purpose=purpose, **extra)
            try:
                return _parse_json(resp.choices[0].message.content)
            except json.JSONDecodeError:
                if attempt == 1:
                    raise
        raise RuntimeError("unreachable")

    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json\n", "", 1)
    return json.loads(raw)