"""The sub-question's own question is judged as the last aspect (TOPIC_ASPECT). Offline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import detail_aspects as da  # noqa: E402

TOPIC = "What is a mixture of experts (MoE) model?"
ASPECTS = ["How does a MoE model differ from a standard model?", "advantages of a MoE model", "disadvantages of a MoE model"]
A2D = [0, 1, 1]
DETAILS = ["How does a MoE model differ from a standard model?", "What are the advantages and disadvantages of a MoE model?"]


def test_off_unless_switched_on(monkeypatch):
    """Default off (2026-11-06): with the topic in the aspect list the digest model returned 65% fewer findings."""
    monkeypatch.delenv("TOPIC_ASPECT", raising=False)
    assert da.topic_aspect_enabled() is False
    assert da.with_topic_aspect(ASPECTS, A2D, DETAILS, TOPIC) == (ASPECTS, A2D, DETAILS)


def test_the_topic_is_appended_as_the_last_aspect_with_its_own_detail(monkeypatch):
    monkeypatch.setenv("TOPIC_ASPECT", "true")
    aspects, a2d, details = da.with_topic_aspect(ASPECTS, A2D, DETAILS, TOPIC)
    assert aspects == ASPECTS + [TOPIC]                  # the other aspects keep their indexes
    assert a2d == A2D + [len(DETAILS)] and details == DETAILS + [TOPIC]
    assert ASPECTS == ASPECTS[:3] and len(DETAILS) == 2  # inputs are not changed


def test_switched_off_nothing_changes(monkeypatch):
    for value in ("false", "0", "off", "no", ""):
        monkeypatch.setenv("TOPIC_ASPECT", value)
        assert da.with_topic_aspect(ASPECTS, A2D, DETAILS, TOPIC) == (ASPECTS, A2D, DETAILS)
    assert da.with_topic_aspect(ASPECTS, A2D, DETAILS, TOPIC, enabled=False) == (ASPECTS, A2D, DETAILS)


def test_an_aspect_that_already_asks_it_is_not_repeated():
    aspects, a2d, details = da.with_topic_aspect(["What is a mixture of experts (MoE) model"], [0], ["d"], TOPIC, enabled=True)
    assert aspects == ["What is a mixture of experts (MoE) model"] and details == ["d"]


def test_empty_topic_adds_nothing():
    assert da.with_topic_aspect(ASPECTS, A2D, DETAILS, "  ", enabled=True)[0] == ASPECTS


def test_the_run_marker():
    assert da.run_topic_aspect(None) is False and da.run_topic_aspect({}) is False
    assert da.run_topic_aspect({"judge_stats": {"yes": 1}}) is False          # a run from before the marker existed
    assert da.run_topic_aspect({"judge_stats": {"topic_aspect": True}}) is True
    assert da.run_topic_aspect({"judge_stats": {"topic_aspect": False}}) is False


def test_the_topic_aspect_counts_in_the_coverage_decision():
    from apps.api.agents.stage3_summarizer import coverage_check as cc
    aspects, a2d, details = da.with_topic_aspect(ASPECTS, A2D, DETAILS, TOPIC, enabled=True)
    digests = [{"source_id": f"s{i}", "findings": []} for i in range(3)]
    result = cc.check_coverage_judged(aspects, a2d, details, digests, {}, candidates=[])
    assert result["sufficient"] is False                                  # nothing was judged for any aspect, the topic included
    assert any(TOPIC in str(x) for x in result.get("uncovered_aspects", []) + result.get("uncovered_details", [])), result.keys()
