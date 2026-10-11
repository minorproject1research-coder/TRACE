from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

# How much one source counts toward `min_sources`, by what its digest was built from. A digest drawn from one abstract
# or a short web snippet is thinner evidence than one drawn from the parsed paper. Digests without an evidence_level
# (older rows) count as full text.
EVIDENCE_WEIGHT = {"full_text": 1.0, "abstract": 0.5, "web_snippet": 0.5}


def check_coverage(detail_questions: list[str], digests: list[dict],
                   min_sources: int = 3, detail_sim: float = 0.6) -> dict:
    """Rule-based: sufficient if the sources with verified findings add up to >= min_sources (full-text papers count 1,
    abstract-only papers and web snippets 0.5) AND every detail question is matched by at least one verified claim."""
    verified = [(d, f) for d in digests for f in d["findings"] if f["verified"]]
    by_source = {}
    for d, _ in verified:
        by_source[d["source_id"]] = d.get("evidence_level") or "full_text"
    weighted_sources = sum(EVIDENCE_WEIGHT.get(level, 1.0) for level in by_source.values())

    if verified and detail_questions:
        m = get_embedder()
        dq = m.encode(detail_questions, normalize_embeddings=True)
        fe = m.encode([f["claim"] for _, f in verified], normalize_embeddings=True)
        sims = dq @ fe.T
        uncovered = [q for i, q in enumerate(detail_questions) if sims[i].max() < detail_sim]
    else:
        uncovered = list(detail_questions)

    return {
        "sufficient": weighted_sources >= min_sources and not uncovered,
        "source_count": len(by_source),
        "full_text_source_count": sum(1 for level in by_source.values() if level == "full_text"),
        "uncovered_details": uncovered,
    }
