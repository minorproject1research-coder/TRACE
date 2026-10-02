# apps/api/agents/stage2_retrieval/relevance_filter.py
import os
import json
import logging
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("apps.api.agents.stage2_retrieval")

client = Groq(api_key=os.environ["GROQ_API_KEY"])

_embedder = None

# Toggle: keep False for now — only the fast embedding filter runs.
USE_LLM_JUDGMENT = False


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


def llm_judge_relevance(sub_question: str, paper: dict) -> dict:
    abstract = (paper.get("abstract") or "")[:1000]
    title = paper.get("title", "")

    prompt = RELEVANCE_JUDGE_PROMPT.format(sub_question=sub_question, title=title, abstract=abstract)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
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
    except Exception as e:
        logger.error("Relevance judgment failed for '%s': %s", title[:50], e)
        return {"relevant": False, "confidence": 0.0, "reason": "judgment_failed"}


# Combined pipeline

def filter_relevant(sub_question: str, papers: list[dict],
                     prefilter_top_k: int = 20, min_similarity: float = 0.56,
                     confidence_threshold: float = 0.6) -> list[dict]:
    shortlist = embedding_prefilter(sub_question, papers, top_k=prefilter_top_k, min_similarity=min_similarity)

    if not USE_LLM_JUDGMENT:
        logger.info("LLM judgment disabled — using embedding-only shortlist of %d papers", len(shortlist))
        return shortlist

    passed = []
    for paper in shortlist:
        verdict = llm_judge_relevance(sub_question, paper)
        paper["relevance_verdict"] = verdict
        paper["relevance_score"] = verdict["confidence"] if verdict["relevant"] else 0.0

        if verdict["relevant"] and verdict["confidence"] >= confidence_threshold:
            passed.append(paper)
        else:
            logger.info("Filtered out '%s' — relevant=%s confidence=%.2f",
                        paper.get("title", "")[:50], verdict["relevant"], verdict["confidence"])

    logger.info("Relevance filter: %d shortlisted -> %d passed LLM threshold", len(shortlist), len(passed))
    return passed


def compute_combined_score(paper: dict) -> dict:
    relevance = paper.get("relevance_score", 0.5)
    reliability = paper.get("reliability_score", 0.5)
    paper["combined_score"] = round(relevance * reliability, 3)
    return paper