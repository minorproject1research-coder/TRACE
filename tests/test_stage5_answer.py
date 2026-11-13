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
    assert s.origin == ORIGIN_TEMPLATE and s.tier == "note" and not s.claim_ids and s.text.startswith("The evidence collected does not settle:")
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


def test_near_duplicate_sentences_of_a_section_are_left_out_and_the_stronger_one_stays():
    a = sent("One source reports that increasing inter-institutional data heterogeneity reduces federated learning performance, while another makes a related point that heterogeneity degrades convergence.", "partly", "a")
    b = sent("One source reports that inter-institutional data heterogeneity degrades federated learning performance and convergence.", "single", "b")
    c = sent("One source reports that differential privacy lowers the accuracy of the final model.", "single", "c")
    kept, dropped = answer.dedupe_section([b, a, c])
    assert [s.job_id for s in kept] == ["a", "c"] and [s.job_id for s in dropped] == ["b"]
    assert answer.dedupe_section([c]) == ([c], [])


def test_the_answer_must_now_draw_on_three_of_the_top_sections():
    body = [{"n": i, "section": i} for i in range(1, 5)]
    titles = {1: "a", 2: "b", 3: "c", 4: "d"}
    assert answer.coverage_problems([{"from_sentences": [1]}, {"from_sentences": [2]}], body, [1, 2, 3, 4], titles)
    assert not answer.coverage_problems([{"from_sentences": [1]}, {"from_sentences": [2]}, {"from_sentences": [3]}], body, [1, 2, 3, 4], titles)


def test_select_parts_picks_the_sentences_closest_to_the_question_for_each_top_section():
    sections = [sec(t) for t in TITLES]
    by = [[sent(f"One source reports background fact {i} {j}.", job=f"b{i}{j}") for j in range(3)] for i in range(5)]
    by[4] = [sent("One source reports that federated learning keeps data local.", "supported", "p0"),
             sent("One source reports a privacy-utility trade-off: stronger privacy lowers the accuracy of the model.", "partly", "p1"),
             sent("One source reports that federated learning keeps data on the owner site.", "supported", "p2")]
    parts = answer.select_parts(Q, sections, by)
    assert len(parts) == 3 and parts[0][0] in (3, 4) and {i for i, _ in parts} == {2 + 1, 4, 0}   # the two background titles ("applications and datasets", "applied") are not parts and all(len(ss) <= 2 for _, ss in parts)
    privacy = dict(parts)[4]
    assert any("trade-off" in s.text for s in privacy)                                  # the trade-off sentence beats the stronger-tier "data stays local" ones
    assert not (len(privacy) == 2 and all("keeps data" in s.text for s in privacy))     # and the two near duplicates do not both go in


def test_part_problems_want_exactly_one_sentence_per_part_and_no_mixing():
    body = [{"n": 1, "section": 3}, {"n": 2, "section": 3}, {"n": 3, "section": 4}, {"n": 4, "section": 2}]
    titles = {2: "x", 3: "compare", 4: "privacy"}
    ok = [{"from_sentences": [1]}, {"from_sentences": [3]}, {"from_sentences": [4]}]
    assert answer.part_problems(ok, body, [3, 4, 2], titles) == []
    mixed = answer.part_problems([{"from_sentences": [1, 3]}, {"from_sentences": [4]}], body, [3, 4, 2], titles)
    assert any(r.startswith("sentence 1:") and "ONE Part" in r for r in mixed) and any("no sentence for the part" in r for r in mixed)
    twice = answer.part_problems([{"from_sentences": [1]}, {"from_sentences": [2]}, {"from_sentences": [3]}], body, [3, 4, 2], titles)
    assert any(r.startswith("sentence 2:") and "already has" in r for r in twice)
    assert not any("no sentence for the part" in r for r in answer.part_problems(ok[:2], body, [3, 4, 2], titles, require_all=False))


def test_the_answer_is_put_in_the_order_of_the_parts():
    body = [{"n": 1, "section": 2}, {"n": 2, "section": 3}, {"n": 3, "section": 4}]
    items = [{"text": "a", "from_sentences": [1]}, {"text": "b", "from_sentences": [3]}, {"text": "c", "from_sentences": [2]}]
    assert [i["text"] for i in answer.order_items(items, body, [3, 4, 2])] == ["c", "b", "a"]


def test_select_parts_by_meaning_uses_the_embedder_and_skips_application_sections():
    import numpy as np
    sections = [sec(t) for t in TITLES]
    sections[2] = sec("How is federated learning applied to medical image analysis?")
    by = [[sent(f"One source reports fact {i} {j}.", job=f"f{i}{j}") for j in range(2)] for i in range(5)]
    by[3] = [sent("One source reports that it wins on every benchmark.", job="x"), sent("One source reports that heterogeneity degrades convergence.", job="y")]

    def embed(texts):                                   # the sentence about heterogeneity is "closest"; everything else is far
        return np.array([[1.0, 0.0] if ("heterogeneity" in t or t == Q or t.startswith("How does federated learning compare")) else [0.0, 1.0] for t in texts])

    parts = dict(answer.select_parts(Q, sections, by, embed=embed))
    assert 2 not in parts                                # the application section is not a part (4 others qualify)
    assert [s.job_id for s in parts[3]] == ["y"]
    assert answer.select_parts(Q, sections, by, embed=lambda texts: (_ for _ in ()).throw(RuntimeError("no model")))   # a broken embedder falls back to words
