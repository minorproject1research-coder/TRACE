from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder


def check_coverage(detail_questions: list[str], digests: list[dict],
                   min_sources: int = 3, detail_sim: float = 0.6) -> dict:
    """Rule-based: sufficient if >= min_sources distinct sources have verified findings
    AND every detail question is matched by at least one verified claim."""
    verified = [(d, f) for d in digests for f in d["findings"] if f["verified"]]
    sources = {d["source_id"] for d, _ in verified}

    if verified and detail_questions:
        m = get_embedder()
        dq = m.encode(detail_questions, normalize_embeddings=True)
        fe = m.encode([f["claim"] for _, f in verified], normalize_embeddings=True)
        sims = dq @ fe.T
        uncovered = [q for i, q in enumerate(detail_questions) if sims[i].max() < detail_sim]
    else:
        uncovered = list(detail_questions)

    return {
        "sufficient": len(sources) >= min_sources and not uncovered,
        "source_count": len(sources),
        "uncovered_details": uncovered,
    }