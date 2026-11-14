import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer
from scopus_router import make_router

API_KEY = os.getenv("API_KEY", "change-me")
MAX_ABSTRACT_CHARS = int(os.getenv("MAX_ABSTRACT_CHARS", "3000"))  # set to the same value as in your notebook
MAX_VERIFY_ITEMS = int(os.getenv("MAX_VERIFY_ITEMS", "64"))
MAX_VERIFY_CONCURRENCY = int(os.getenv("MAX_VERIFY_CONCURRENCY", "8"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "1500"))
MAX_FIELD_CHARS = int(os.getenv("MAX_FIELD_CHARS", "1200"))  # claim, quote and aspect are cut to this

# One vLLM server serves both models:
#   "judge"   = the plain Qwen3.5-9B base model
#   "planner" = your LoRA adapter applied on top of the same base weights
VLLM_URL = os.getenv("VLLM_URL", "http://vllm:8000")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "planner")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "judge")
PLANNER_DIR = os.getenv("PLANNER_DIR", "/planner-merged")  # only the tokenizer is read from here

http = httpx.Client(base_url=VLLM_URL, timeout=600)
tok = AutoTokenizer.from_pretrained(PLANNER_DIR)

# ---------------------------------------------------------------- prompts
SYSTEM_PROMPT = (
    "You are a research question decomposition agent. Given a research "
    "question, break it into topic-grouped sub-questions with detail "
    "questions, and provide search ready queries."
)

JUDGE_PROMPT = """You are judging whether a research paper is relevant to a specific research question, based only on its title and abstract.

Research question: {sub_question}

Paper title: {title}
Paper abstract: {abstract}

Judge if this paper is directly relevant and useful as evidence for answering the research question.
Return ONLY a JSON object, nothing else, in this exact format:
{{"relevant": true or false, "confidence": a number between 0 and 1, "reason": "one short sentence"}}
"""

VERIFY_PROMPT = """You are an evidence checker for a research assistant. You are given a research aspect (a question to answer), a claim extracted from a paper, the exact quote it was based on, and optionally the passage around the quote.

Aspect: {aspect}
Claim: {claim}
Quote: {quote}
Surrounding passage (may be empty): {context}

Answer two questions.

1. quote_supports_claim. Does the quote itself state what the claim says? Use the passage only to work out what words such as "it", "our method" or table columns refer to.
   yes = the claim is a faithful restatement of the quote.
   partial = the quote supports only part of the claim, or the claim generalizes (for example "generally", "always"), adds details, names a subject the quote does not mention, or draws an inference the quote does not state.
   no = the quote does not say this. This includes quotes that are only table fragments, headers or captions that do not state the claimed meaning.

2. answers_aspect. Would the claim, on its own, be an acceptable one-sentence answer to the aspect?
   First decide what KIND of answer the aspect asks for, for example: a definition, a way of measuring, the factors or causes of something, the components or parts, the motivation or goal, how something works, results or evidence, advantages or disadvantages, examples, challenges or limitations. Then decide what KIND of statement the claim is. The claim answers the aspect only if it is that kind of statement, about the same subject.
   yes = the claim is the kind of answer the aspect asks for, about the same subject, and complete enough to stand alone as the answer. When the aspect asks for examples, items, advantages, metrics and similar lists, one concrete valid item counts as yes.
   partial = related but incomplete, vague, or only touches the topic; or it gives one half of a two-part aspect; or it is the right kind of answer but about a variant, a specific system or a special case when the aspect asks about the topic in general.
   no = it is about a different subject, a different kind of thing than the aspect asks for, or only shares vocabulary with the aspect.

   These are NOT answers, even when they are true and on topic:
   - A cause, reason or source of something is not its definition and not a way of measuring it. A result or number is not a way of measuring, a definition, or a factor, unless the claim says that this is the factor or the measure.
   - A description of how a method works is not the motivation for it, and a motivation is not a description of how it works.
   - A list of things or a process is not "the components" unless the claim names the parts the thing is made of. A training procedure, a list of properties used to compare models, or the parts of a different system are not the components of the subject.
   - A fix, mitigation or improvement is not an account of the problem it addresses, and a statement of a problem is not an account of its fix.
   - A claim about a different system or modality than the one the aspect asks about is "no" unless the aspect is general. A claim about a named variant of the subject is at most "partial" when the aspect is about the subject in general.
   Examples on an unrelated topic, to show the rule: for the aspect "how the size of a database index is measured", the claim "indexes slow down writes because every insert must update them" is "no" (a consequence, not a measurement); for "components of a database index", the claim "an index is built with a sorted copy of one column plus row pointers" is "yes", and "indexes are created by running a CREATE INDEX statement" is "no" (a procedure, not components); for "motivation of caching", the claim "a cache stores results in a hash table" is "no" (how it works), and "caches avoid recomputing results that are requested again, which saves time" is "yes".

Be strict. Sharing words with the aspect is not an answer. Return ONLY a JSON object, nothing else, in this exact format:
{{"quote_supports_claim": "yes" or "partial" or "no", "answers_aspect": "yes" or "partial" or "no", "reason": "one short sentence"}}
"""

def parse_verdict(raw):
    """Pull the verdict JSON out of a reply (tolerates <think> blocks, code fences, extra prose). None if unusable."""
    if not raw:
        return None
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    candidates = [text]
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        c = c.strip().strip("`")
        if c.startswith("json"):
            c = c[4:]
        try:
            obj = json.loads(c)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("relevant"), bool):
            try:
                conf = float(obj.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            return {"relevant": obj["relevant"], "confidence": min(max(conf, 0.0), 1.0),
                    "reason": str(obj.get("reason", ""))}
    return None


_EVIDENCE_ANSWERS = {"yes", "partial", "no"}


def evidence_final(quote_supports_claim, answers_aspect):
    """Computed in code, never taken from the model."""
    if quote_supports_claim == "yes" and answers_aspect == "yes":
        return "yes"
    if quote_supports_claim == "no" or answers_aspect == "no":
        return "no"
    return "partial"


def parse_evidence_verdict(raw):
    """Pull the evidence verdict out of a reply (tolerates <think> blocks, code fences, extra prose).
    None if unusable, including any answer that is not yes/partial/no.
    A reply that is only missing its final closing brace is accepted."""
    if not raw:
        return None
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    candidates = [text]
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        candidates.append(m.group(0))
    # The model sometimes stops one token early and leaves out the closing brace.
    # Repair only that case: an object whose last character is a closing quote and
    # which is missing exactly one "}". The answers are still validated below.
    start = text.find("{")
    if start != -1:
        tail = text[start:].rstrip().rstrip("`").rstrip()
        if tail.endswith('"') and tail.count("{") == tail.count("}") + 1:
            candidates.append(tail + "}")
    for c in candidates:
        c = c.strip().strip("`")
        if c.startswith("json"):
            c = c[4:]
        try:
            obj = json.loads(c)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        q, a = obj.get("quote_supports_claim"), obj.get("answers_aspect")
        q = q.strip().lower() if isinstance(q, str) else None
        a = a.strip().lower() if isinstance(a, str) else None
        if q in _EVIDENCE_ANSWERS and a in _EVIDENCE_ANSWERS:
            reason = obj.get("reason", "")
            return {"quote_supports_claim": q, "answers_aspect": a,
                    "final": evidence_final(q, a),
                    "reason": "" if reason is None else str(reason)}
    return None


app = FastAPI()


def check_key(x_api_key):
    if x_api_key != API_KEY:
        raise HTTPException(401, "bad key")

app.include_router(make_router(check_key))
def vllm_post(path, payload):
    try:
        r = http.post(path, json=payload)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"vLLM unreachable: {e}")
    if r.status_code != 200:
        raise HTTPException(502, f"vLLM error: {r.text}")
    return r.json()


# ---------------------------------------------------------------- endpoints
class DecomposeReq(BaseModel):
    question: str
    max_new_tokens: int = 768
    ckpt_path: str | None = None  # accepted for compatibility, ignored
    temperature: float | None = None   # None -> 0.3, the current value
    top_p: float | None = None         # None -> 0.9
    n: int = 1                         # number of alternative plans
    seed: int | None = None


@app.post("/decompose")
def decompose(req: DecomposeReq, x_api_key: str = Header(None)):
    check_key(x_api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.question},
    ]
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    prompt += "<think>\n\n</think>\n\n"
    body = {
        "model": PLANNER_MODEL, "prompt": prompt, "max_tokens": req.max_new_tokens,
        "temperature": 0.3 if req.temperature is None else min(max(req.temperature, 0.0), 1.2),
        "top_p": 0.9 if req.top_p is None else req.top_p,
        "n": min(max(req.n, 1), 4),
    }
    if req.seed is not None:
        body["seed"] = req.seed
    data = vllm_post("/v1/completions", body)
    outputs = [c["text"].strip() for c in data["choices"]]
    return {"raw_output": outputs[0], "raw_outputs": outputs, "ckpt_path": PLANNER_MODEL}

class JudgeReq(BaseModel):
    sub_question: str
    title: str
    abstract: str | None = ""
    max_new_tokens: int = 256
    thinking: bool = False  # Qwen3.5 thinking mode; off = faster, JSON only


@app.post("/judge")
def judge(req: JudgeReq, x_api_key: str = Header(None)):
    check_key(x_api_key)
    prompt = JUDGE_PROMPT.format(
        sub_question=req.sub_question, title=req.title,
        abstract=(req.abstract or "")[:MAX_ABSTRACT_CHARS])
    data = vllm_post("/v1/chat/completions", {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": req.max_new_tokens,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": req.thinking}})
    raw = (data["choices"][0]["message"]["content"] or "").strip()
    return {"verdict": parse_verdict(raw), "raw_output": raw}


# ---------------------------------------------------------------- evidence judge
def _cut(text, limit):
    return (text or "")[:limit]


def run_verify(aspect, claim, quote, context, max_new_tokens, thinking):
    """One evidence check against the base judge model. Raises HTTPException (502) if vLLM fails."""
    prompt = VERIFY_PROMPT.format(
        aspect=_cut(aspect, MAX_FIELD_CHARS), claim=_cut(claim, MAX_FIELD_CHARS),
        quote=_cut(quote, MAX_FIELD_CHARS), context=_cut(context, MAX_CONTEXT_CHARS))
    data = vllm_post("/v1/chat/completions", {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_new_tokens,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": thinking}})
    raw = (data["choices"][0]["message"]["content"] or "").strip()
    return {"verdict": parse_evidence_verdict(raw), "raw_output": raw}


class VerifyReq(BaseModel):
    aspect: str
    claim: str
    quote: str
    context: str = ""
    max_new_tokens: int = 200
    thinking: bool = False


class VerifyItem(BaseModel):
    id: str
    aspect: str
    claim: str
    quote: str
    context: str = ""


class VerifyBatchReq(BaseModel):
    items: list[VerifyItem]
    max_new_tokens: int = 200
    thinking: bool = False


@app.post("/verify_evidence")
def verify_evidence(req: VerifyReq, x_api_key: str = Header(None)):
    check_key(x_api_key)
    return run_verify(req.aspect, req.claim, req.quote, req.context,
                      req.max_new_tokens, req.thinking)


@app.post("/verify_evidence_batch")
def verify_evidence_batch(req: VerifyBatchReq, x_api_key: str = Header(None)):
    check_key(x_api_key)
    if len(req.items) > MAX_VERIFY_ITEMS:
        raise HTTPException(422, f"too many items: {len(req.items)} > {MAX_VERIFY_ITEMS}")

    def one(item):
        try:
            out = run_verify(item.aspect, item.claim, item.quote, item.context,
                             req.max_new_tokens, req.thinking)
            return {"id": item.id, "verdict": out["verdict"],
                    "raw_output": out["raw_output"], "error": None}
        except HTTPException as e:
            return {"id": item.id, "verdict": None, "raw_output": "", "error": str(e.detail)}
        except Exception as e:  # one bad item must not fail the batch
            return {"id": item.id, "verdict": None, "raw_output": "",
                    "error": f"{type(e).__name__}: {e}"}

    # vLLM batches the concurrent requests itself; ex.map keeps the input order
    with ThreadPoolExecutor(max_workers=max(1, MAX_VERIFY_CONCURRENCY)) as ex:
        results = list(ex.map(one, req.items))
    return {"results": results}


@app.delete("/model")
def delete_model(x_api_key: str = Header(None)):
    """Kept so existing clients don't break. Both models share one server, so there is nothing to unload."""
    check_key(x_api_key)
    return {"unloaded": False, "note": "single shared vLLM server; nothing to unload"}


@app.get("/status")
def status(x_api_key: str = Header(None)):
    check_key(x_api_key)
    try:
        r = http.get("/v1/models")
        models = [m["id"] for m in r.json().get("data", [])] if r.status_code == 200 else []
        return {"vllm_up": r.status_code == 200, "models": models}
    except httpx.HTTPError:
        return {"vllm_up": False, "models": []}