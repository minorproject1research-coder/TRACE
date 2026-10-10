# apps/api/agents/stage2_retrieval/relevance_filter.py
import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

from apps.api.services import trace_llm_service

load_dotenv()

logger = logging.getLogger("apps.api.agents.stage2_retrieval")

client = Groq(api_key=os.environ["GROQ_API_KEY"])

_embedder = None

# Toggle: get value from environment variable (default: false) — only the fast embedding filter runs.
USE_LLM_JUDGMENT = os.environ.get("USE_LLM_JUDGMENT", "false").lower() == "true"

# Where the judge runs: "server" = the fine-tuned-stack model server (POST /judge, Qwen3.5-9B on vLLM over Tailscale);
# "groq" = the old Groq placeholder only.
JUDGE_BACKEND = os.environ.get("JUDGE_BACKEND", "server").lower()
# If the model server fails for a paper: "groq" = ask the Groq placeholder instead; "none" = give up on that paper.
LLM_FALLBACK = os.environ.get("TRACE_LLM_FALLBACK", "groq").lower()
# Papers judged in parallel (the server handles up to 32 concurrent requests; 12 parallel calls took ~5 s in total).
JUDGE_WORKERS = max(1, int(os.environ.get("JUDGE_WORKERS", "8")))
# Groq model used when the server is unavailable. The old placeholder llama-3.1-8b-instant was removed from Groq (HTTP 404).
GROQ_JUDGE_MODEL = os.environ.get("GROQ_JUDGE_MODEL", "openai/gpt-oss-120b")

# Max abstract characters shown to the LLM judge. The benchmark (evaluation/relevance_judge) and its
# pre-labeler import this same value, so labels and models always see identical text. 2500 covers ~99.7%
# of real abstracts (median ~1300) while capping the rare multi-thousand-character OpenAlex ones;
# the old 1000-char cut dropped the methods/results half of ~80% of abstracts.
JUDGE_ABSTRACT_CHAR_LIMIT = 2500


def get_embedder():
    """Lazy-loads the embedding model once, reused across all calls."""
    global _embedder
    if _embedder is None:
        logger.info("Loading embedding model BAAI/bge-base-en-v1.5")
        _embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _embedder


# Stage 1: Embedding pre-filter (always runs, fast, on all candidates)

def embedding_prefilter(sub_question: str, papers: list[dict],
                         top_k: int = 20, min_similarity: float = 0.5) -> list[dict]:
    """Ranks papers by cosine similarity (sub-question vs abstract).
    Only papers clearing min_similarity are kept, then capped at top_k."""
    if not papers:
        return []

    model = get_embedder()
    texts = [p.get("abstract") or p.get("title", "") for p in papers]

    query_emb = model.encode([sub_question], normalize_embeddings=True)[0]
    doc_embs = model.encode(texts, normalize_embeddings=True)

    similarities = doc_embs @ query_emb

    for paper, sim in zip(papers, similarities):
        paper["embedding_similarity"] = float(round(sim, 4))
        paper["relevance_score"] = paper["embedding_similarity"]

    qualified = [p for p in papers if p["embedding_similarity"] >= min_similarity]
    ranked = sorted(qualified, key=lambda p: p["embedding_similarity"], reverse=True)

    logger.info("Embedding pre-filter: %d candidates -> %d cleared min_similarity (%.2f) -> top %d shortlisted",
                len(papers), len(qualified), min_similarity, min(top_k, len(ranked)))
    return ranked[:top_k]


# Stage 2: LLM relevance judgment (optional, only on shortlist)

RELEVANCE_JUDGE_PROMPT = """You are judging whether a research paper is relevant to a specific research question, based only on its title and abstract.

Research question: {sub_question}

Paper title: {title}
Paper abstract: {abstract}

Judge if this paper is directly relevant and useful as evidence for answering the research question.
Return ONLY a JSON object, nothing else, in this exact format:
{{"relevant": true or false, "confidence": a number between 0 and 1, "reason": "one short sentence"}}
"""


def _groq_judge(sub_question: str, title: str, abstract: str) -> dict:
    """Fallback judge on Groq (model: GROQ_JUDGE_MODEL). Raises on any failure."""
    prompt = RELEVANCE_JUDGE_PROMPT.format(sub_question=sub_question, title=title, abstract=abstract)
    response = client.chat.completions.create(
        model=GROQ_JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json\n", "", 1)
    verdict = json.loads(raw)
    return {
        "relevant": bool(verdict.get("relevant", False)),
        "confidence": float(verdict.get("confidence", 0.0)),
        "reason": str(verdict.get("reason", "")),
    }


def llm_judge_relevance(sub_question: str, paper: dict) -> dict | None:
    """Verdict {"relevant", "confidence", "reason"}, or None if every backend failed.

    None means "no opinion": filter_relevant keeps such a paper (decided by the embedding filter alone) instead of
    treating a broken judge as a rejection."""
    abstract = (paper.get("abstract") or "")[:JUDGE_ABSTRACT_CHAR_LIMIT]
    title = paper.get("title", "")

    if JUDGE_BACKEND == "server":
        try:
            return trace_llm_service.judge(sub_question, title, abstract)
        except trace_llm_service.TraceLLMError as e:
            logger.warning("Judge server failed for '%s': %s", title[:50], e)
            if LLM_FALLBACK != "groq":
                return None

    try:
        return _groq_judge(sub_question, title, abstract)
    except Exception as e:
        logger.error("Relevance judgment failed for '%s': %s", title[:50], e)
        return None


# Combined pipeline

def filter_relevant(sub_question: str, papers: list[dict],
                     prefilter_top_k: int = 20, min_similarity: float = 0.56,
                     confidence_threshold: float = 0.6) -> list[dict]:
    shortlist = embedding_prefilter(sub_question, papers, top_k=prefilter_top_k, min_similarity=min_similarity)

    if not USE_LLM_JUDGMENT:
        logger.info("LLM judgment disabled — using embedding-only shortlist of %d papers", len(shortlist))
        return shortlist

    # judge the shortlist in parallel; results keep the shortlist order
    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        verdicts = list(pool.map(lambda p: llm_judge_relevance(sub_question, p), shortlist))

    passed, no_opinion = [], 0
    for paper, verdict in zip(shortlist, verdicts):
        if verdict is None:                      # judge unavailable: fail open, keep the embedding-based decision
            no_opinion += 1
            paper["relevance_verdict"] = {"reason": "judgment_failed"}
            passed.append(paper)
            continue

        paper["relevance_verdict"] = verdict
        paper["relevance_score"] = verdict["confidence"] if verdict["relevant"] else 0.0

        if verdict["relevant"] and verdict["confidence"] >= confidence_threshold:
            passed.append(paper)
        else:
            logger.info("Filtered out '%s' — relevant=%s confidence=%.2f",
                        paper.get("title", "")[:50], verdict["relevant"], verdict["confidence"])

    logger.info("Relevance filter [%s judge]: %d shortlisted -> %d passed (%d kept without a judgment)",
                JUDGE_BACKEND, len(shortlist), len(passed), no_opinion)
    return passed


def compute_combined_score(paper: dict) -> dict:
    relevance = paper.get("relevance_score", 0.5)
    reliability = paper.get("reliability_score", 0.5)
    paper["combined_score"] = round(relevance * reliability, 3)
    return paper