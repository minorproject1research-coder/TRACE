# apps/api/services/text_norm.py
"""Word-level normalization shared by the places that decide whether two questions are "the same".

Two questions count as identical only when they use the same content words once stop words, case, punctuation and a plural "s" are
ignored. Embedding similarity is NOT used for that decision: questions about one topic share most of their words, so different
questions score 0.93-0.99 ("compare in memory cost" / "compare in performance" 0.95), and merging them silently removed part of what the
user asked. See stage3_summarizer.detail_aspects.merge_mode and stage1_planner.question_generator."""
import re

STOP_WORDS = frozenset({"the", "a", "an", "of", "and", "or", "for", "in", "on", "to", "is", "are", "what", "how", "do", "does", "with", "from", "by", "as",
                        "at", "be", "this", "that", "these", "those", "their", "its", "which", "can", "some", "common"})


def normalized_words(text: str) -> frozenset:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words if w not in STOP_WORDS)
