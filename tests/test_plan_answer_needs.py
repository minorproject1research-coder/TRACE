"""The answer-needs step of the planner (answer_needs.py): extra sub-questions for conditions, risks and figures, within the sub-question cap."""
import json

import pytest

from apps.api.agents.stage1_planner import answer_needs as an
from apps.api.agents.stage1_planner import plan_cache, question_generator as qg
from apps.api.services import trace_llm_service as t

Q = "How effective is federated learning compared with centralized training for medical image analysis, and what are the privacy trade-offs?"
SQS = [("What is federated learning and how does it differ from centralized training?", ["a"]),
       ("What is medical image analysis and what are the common applications and datasets?", ["b"]),
       ("How is federated learning applied to medical image analysis?", ["c"]),
       ("How does federated learning compare with centralized training for medical image analysis?", ["d"]),
       ("What are the privacy trade-offs of federated learning for medical image analysis?", ["e"])]
NEW = {"sub_questions": [{"topic": "Under what conditions does federated learning fall short of centralized training for medical image analysis, and by how much?",
                          "details": ["How does non-IID site data change the gap?", "How does the number of sites change it?"]},
                         {"topic": "Which privacy attacks on federated medical imaging are documented and which defences reduce them at what cost?",
                          "details": ["gradient inversion", "differential privacy accuracy cost"]}],
       "search_queries": ["federated learning non-IID medical imaging benchmark", "gradient inversion attack federated medical images empirical",
                          "differential privacy federated learning chest x-ray accuracy cost"]}


def plan():
    return {"sub_questions": [{"topic": s, "details": d} for s, d in SQS], "search_queries": ["q1", "q2"]}


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setenv("PLAN_ANSWER_SUBQUESTIONS", "2")


def test_two_sub_questions_are_added_and_the_definitional_background_makes_room():
    p, info = an.augment(Q, plan(), 5, chat=lambda prompt: json.dumps(NEW))
    topics = [s["topic"] for s in p["sub_questions"]]
    assert len(topics) == 5 and topics[-2:] == info["added"]
    assert len(info["dropped"]) == 2 and all(d.startswith("What is") for d in info["dropped"])
    assert SQS[3][0] in topics and SQS[4][0] in topics and SQS[2][0] in topics          # the comparison, the privacy and the application questions stay
    assert p["search_queries"][:2] == ["q1", "q2"] and len(p["search_queries"]) == 5
    assert p["answer_needs"] == {"added": info["added"], "dropped": info["dropped"]}


def test_a_plan_with_room_only_gets_additions():
    small = {"sub_questions": [{"topic": s, "details": d} for s, d in SQS[3:]], "search_queries": []}
    p, info = an.augment(Q, small, 5, chat=lambda prompt: json.dumps(NEW))
    assert len(p["sub_questions"]) == 4 and info["dropped"] == []


def test_an_existing_sub_question_is_never_repeated_and_a_core_question_is_never_dropped():
    reply = {"sub_questions": [{"topic": SQS[3][0], "details": ["x"]}, NEW["sub_questions"][0]], "search_queries": []}
    full = {"sub_questions": [{"topic": s, "details": d} for s, d in SQS[2:]] * 1 + [{"topic": "How does federated learning scale across sites for medical image analysis?", "details": ["z"]},
                                                                                      {"topic": "How do privacy trade-offs of federated learning for medical image analysis arise?", "details": ["y"]}],
            "search_queries": []}
    p, info = an.augment(Q, full, 5, chat=lambda prompt: json.dumps(reply))
    assert len(p["sub_questions"]) <= 5
    assert [s["topic"] for s in p["sub_questions"]].count(SQS[3][0]) == 1
    assert SQS[3][0] in [s["topic"] for s in p["sub_questions"]]


def test_a_marker_means_nothing_is_called_again():
    p = plan()
    p["answer_needs"] = {"added": ["x"], "dropped": ["y"]}
    p2, info = an.augment(Q, p, 5, chat=lambda prompt: pytest.fail("must not call the model again"))
    assert info == {"added": ["x"], "dropped": ["y"], "stored": True} and p2 is p


def test_a_failure_or_a_bad_reply_or_zero_leaves_the_plan_alone(monkeypatch):
    for chat in (lambda prompt: (_ for _ in ()).throw(RuntimeError("down")), lambda prompt: "not json at all", lambda prompt: json.dumps({"sub_questions": []})):
        p, info = an.augment(Q, plan(), 5, chat=chat)
        assert info is None and p["sub_questions"] == plan()["sub_questions"] and "answer_needs" not in p
    monkeypatch.setenv("PLAN_ANSWER_SUBQUESTIONS", "0")
    p, info = an.augment(Q, plan(), 5, chat=lambda prompt: pytest.fail("off"))
    assert info is None


def test_generate_uses_and_stores_the_augmented_plan(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "true")
    calls = []
    monkeypatch.setattr(t, "decompose", lambda q, **k: (calls.append(q), plan())[1])
    real = an.augment
    monkeypatch.setattr(an, "augment", lambda q, p, cap, chat=None: real(q, p, cap, chat=lambda prompt: json.dumps(NEW)))
    monkeypatch.setattr(qg, "_assign_queries", lambda sqs, queries: None)
    out = qg.generate(Q)
    assert len(out) == 5 and qg.plan_notes(Q)["added"]
    stored = plan_cache.load(Q)
    assert stored and stored["answer_needs"]["added"]                       # a rerun reuses the same augmented plan



def test_a_copied_label_is_stripped_from_the_topic():
    reply = {"sub_questions": [{"topic": "Conditions and limits: When does federated learning underperform centralized training for medical image analysis?", "details": []},
                               {"topic": "B. Risks, costs and defences: Which privacy attacks on federated medical imaging are documented?", "details": []}], "search_queries": []}
    new, _ = an._validated(reply, [], 2)
    assert new[0]["topic"].startswith("When does federated learning") and new[1]["topic"].startswith("Which privacy attacks")
