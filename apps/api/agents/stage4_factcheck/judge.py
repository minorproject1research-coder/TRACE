import logging

from apps.api.services.llm_service import squeezer_json

logger = logging.getLogger("apps.api.agents.stage4_factcheck")

PROMPT = """You compare two statements from different research sources.

Statement A: {claim}
Evidence from source B: "{quote}"
Source B's claim: {other_claim}

Decide whether the two sources DIRECTLY CONTRADICT each other.
Apply this test: could both statements be true at the same time?
- If yes (different scope, different language, dataset or setting, different metric, or one
  is just more specific), they do NOT conflict.
- Only answer conflicts=true if they assert opposite things about the SAME subject, the same
  property and the same setting.
- Do not stretch wording: related topics or loosely similar terms (e.g. "accuracy" vs "fitness")
  are not the same aspect.

Return ONLY JSON: {{"same_aspect": true, "conflicts": true, "confidence": 0.0, "reason": "one sentence"}}
(use true/false for the first two fields and a number from 0 to 1 for confidence)"""


def judge_conflict(claim: str, quote: str, other_claim: str) -> dict:
    try:
        v = squeezer_json(PROMPT.format(claim=claim, quote=quote, other_claim=other_claim))
        return {
            "same_aspect": bool(v.get("same_aspect")),
            "conflicts": bool(v.get("conflicts")),
            "confidence": float(v.get("confidence", 0.0)),
            "reason": str(v.get("reason", "")),
        }
    except Exception as e:
        logger.warning("Conflict judge failed: %s", e)
        return {"same_aspect": False, "conflicts": False, "confidence": 0.0,
                "reason": f"judge failed: {e}"}
        
        
SUPPORT_PROMPT = """Quote from a research source: "{quote}"
Claim: "{claim}"

Does the quote support the claim?
- Yes only if everything the claim asserts is stated or clearly implied by the quote.
- No if the claim adds a fact, number, cause, comparison or detail that the quote does not contain.
- The quote comes from a paper about the claim's topic, so it need not repeat the topic's name.
- Ignore formatting noise in the quote (figure labels, stray symbols, broken spacing).

Return ONLY JSON: {{"supports": true, "confidence": 0.0, "reason": "one sentence"}}
(use true or false for supports, and a number from 0 to 1 for confidence)"""


def judge_support(claim: str, quote: str) -> dict:
    try:
        v = squeezer_json(SUPPORT_PROMPT.format(claim=claim, quote=quote))
        return {
            "supports": bool(v.get("supports")),
            "confidence": float(v.get("confidence", 0.0)),
            "reason": str(v.get("reason", "")),
        }
    except Exception as e:
        logger.warning("Support judge failed: %s", e)
        return {"supports": False, "confidence": 0.0, "reason": f"judge failed: {e}"}
    
SAME_PROMPT = """Two claims from different research sources.

Claim 1: "{a}"
Claim 2: "{b}"

Do they make the SAME specific assertion? Answer yes only if someone who believes one claim
would necessarily believe the other.
Answer no if:
- one gives a mechanism, cause, number, condition or scope that the other lacks
- one is a general statement ("it is faster") and the other a specific one
- they cover different aspects (speed vs memory vs cost vs challenges)

Return ONLY JSON: {{"same": true, "reason": "one sentence"}}
(use true or false for same)"""


def judge_same_claim(a: str, b: str) -> bool:
    try:
        v = squeezer_json(SAME_PROMPT.format(a=a, b=b))
        return bool(v.get("same"))
    except Exception as e:
        logger.warning("Same-claim judge failed: %s", e)
        return False    # on failure do not merge