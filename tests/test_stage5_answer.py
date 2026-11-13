"""The answer block of Stage 5 (answer.py): which sections matter for the question, which sentences feed the answer, the coverage check."""
from types import SimpleNamespace

from apps.api.agents.stage5_report import answer
from apps.api.agents.stage5_report.schema import ORIGIN_TEMPLATE, Sentence

Q = "How effective is federated learning compared with centralized training for medical image analysis, and what are the privacy trade-offs?"
TITLES = ["What is federated learning and how does it differ from centralized training?",
          "What is medical image analysis and what are the common applications and datasets?",
          "How is federated learning applied to medical image analysis?",
          "How does federated learning compare with centralized training for medical image analysis?",
          "What are the privacy trade-offs of federated learning for medical image analysis?"]


def sec(title):
    return SimpleNamespace(title=title, detail_questions=[])


def sent(text, tier="partly", job="j"):
    return Sentence(text=text, claim_ids=[job], job_id=job, tier=tier)


def test_the_comparison_and_the_privacy_sections_rank_first_and_background_last():
    scores = answer.section_scores(Q, [sec(t) for t in TITLES])
    order = sorted(range(5), key=lambda i: -scores[i])
    assert set(order[:2]) == {3, 4} and order[-1] in (0, 1)


def test_candidates_come_from_the_top_sections_figures_first_and_the_rest_goes_to_the_conclusion():
    sections = [sec(t) for t in TITLES]
    by = [[sent(f"One source reports background {i} {j}.", job=f"b{i}{j}") for j in range(3)] for i in range(5)]
    by[3] = [sent("One source reports that it is comparable.", job="c0"), sent("One source reports a 2.1% Dice gap to pooled training.", job="c1"),
             sent("Two sources report that it scales.", tier="supported", job="c2")] + [sent(f"One source reports extra {k}.", "single", f"c{k + 3}") for k in range(4)]
    cand, spare, top = answer.candidates(Q, sections, by, limit=12)
    texts = [s.text for s in cand]
    assert top[0] in (3, 4) and 3 in top
    assert "Two sources report that it scales." in texts and "One source reports a 2.1% Dice gap to pooled training." in texts
    assert len(cand) <= 12 and not ({id(s) for s in cand} & {id(s) for s in spare})


def test_coverage_check_asks_for_the_missing_section_and_passes_when_enough_are_used():
    body = [{"n": 1, "section": 3}, {"n": 2, "section": 3}, {"n": 3, "section": 4}, {"n": 4, "section": 0}]
    titles = {3: "compare", 4: "privacy"}
    assert answer.coverage_problems([{"from_sentences": [1]}, {"from_sentences": [2, 4]}], body, [3, 4], titles)
    assert not answer.coverage_problems([{"from_sentences": [1]}, {"from_sentences": [3]}], body, [3, 4], titles)
    assert "privacy" in answer.coverage_problems([{"from_sentences": [1, 2]}], body, [3, 4], titles)[0]
    assert answer.coverage_problems([{"from_sentences": [1]}], body, [], titles) == []


def test_gap_sentence_names_what_the_evidence_does_not_settle_and_is_a_template():
    gaps = [["The collected evidence does not sufficiently answer: How does centralized training affect accuracy?", "3 claims not used: x"],
            ["The collected evidence does not sufficiently answer: How does centralized training expose privacy risks?; How does it expose security risks?"]]
    s = answer.gap_sentence(gaps)
    assert s.origin == ORIGIN_TEMPLATE and not s.claim_ids and s.text.startswith("The evidence collected does not settle:")
    assert "privacy risks" in s.text and "accuracy" in s.text
    assert answer.gap_sentence([["3 claims not used"]]) is None


def test_a_summary_may_drop_without_but_not_not():
    from apps.api.agents.stage5_report import validators
    body = [{"n": 1, "text": "One source reports that hospitals collaborate without centralizing data.", "tier": "single"},
            {"n": 2, "text": "One source reports that the gain is not significant.", "tier": "single"}]
    ok = validators.check_summary([{"text": "One source reports that hospitals collaborate across institutions.", "from_sentences": [1]}], body, min_sentences=1, max_sentences=5)
    bad = validators.check_summary([{"text": "One source reports that the gain is significant.", "from_sentences": [2]}], body, min_sentences=1, max_sentences=5)
    assert not any("negation" in r for r in ok) and any("negation" in r for r in bad)


def test_a_rejected_answer_keeps_the_sentences_that_passed():
    from apps.api.agents.stage5_report import summary
    body = [{"n": 1, "text": "One study reports that A is high.", "tier": "single", "claim_ids": ["a"], "job_id": "j1", "section": 0},
            {"n": 2, "text": "One study reports that B is low.", "tier": "single", "claim_ids": ["b"], "job_id": "j2", "section": 1},
            {"n": 3, "text": "One study reports that C is mid.", "tier": "single", "claim_ids": ["c"], "job_id": "j3", "section": 1}]
    items = [{"text": "One study reports that A is high.", "from_sentences": [1]}, {"text": "B is low.", "from_sentences": [2]},
             {"text": "One study reports that C is mid.", "from_sentences": [3]}]
    check = lambda its, b, min_sentences=None: [] if all(i["text"].startswith("One study") for i in its) else ["sentence 2: stronger"]      # noqa: E731
    kept = summary._salvage("conclusion", items, ["sentence 2: stronger"], body, check)
    assert [i["from_sentences"] for i in kept] == [[1], [3]]
    assert summary._salvage("conclusion", items, ["write between 4 and 6 sentences; you wrote 3"], body, check) == []        # not about one sentence
    assert summary._salvage("conclusion", items[:2], ["sentence 2: stronger"], body, check) == []                            # too few left
