"""Stage 4 (fact checking) without models or network: hand-made claims, a fake embedder, fake NLI and fake judges.
Checks the rules of the handoff report (docs/reports/TRACE Stage 4 Fact Checking, Handoff Report.md, section 11): judges fail closed, an
unverified claim is never "supported", NLI alone never declares a conflict, and the results do not depend on thread timing."""
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage4_factcheck import common, contradiction_detector as cd, fact_checker as fc, judge  # noqa: E402


# ---------------------------------------------------------------------------------------------------------------- fakes
class FakeEmbedder:
    """The first word is the topic (one axis each). '@a' / '@b' in the text adds a small component on a second axis: same topic and same
    marker = identical vectors (cosine 1.0, auto-merge), same topic and different marker = cosine 0.89 (the judge's gray zone),
    different topic = 0."""
    TOPICS = {"speed": 0, "memory": 1, "quality": 2, "quote": 3}

    def encode(self, texts, normalize_embeddings=True):
        out = []
        for t in texts:
            v = np.zeros(8, dtype=np.float32)
            v[self.TOPICS.get(t.split()[0].split("@")[0], 4)] = 1.0
            if "@a" in t.split()[0]:
                v[6] = 0.35
            elif "@b" in t.split()[0]:
                v[7] = 0.35
            out.append(v / np.linalg.norm(v))
        return np.array(out)


@pytest.fixture(autouse=True)
def fakes(monkeypatch, tmp_path):
    monkeypatch.setattr(fc, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(cd, "get_embedder", lambda: FakeEmbedder())
    monkeypatch.setenv("STAGE4_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("STAGE4_CACHE", "false")
    monkeypatch.setenv("STAGE4_WORKERS", "3")


def claim(text, doc, weight=0.6, ev=1.0, source=None, quote=None):
    return {"claim": text, "quote": quote or f"quote of {text}", "source_id": source or doc, "source_title": doc, "doc": doc,
            "reliability": weight, "evidence_level": "full_text", "ev": ev, "weight": weight}


# ---------------------------------------------------------------------------------------------------------- load_claims
def digest(source, title, findings, level="full_text", rel=0.8):
    return {"source_id": source, "source_title": title, "evidence_level": level, "reliability": rel, "findings": findings}


def test_load_claims_keeps_only_verified_grounded_claims_with_quotes():
    d = [digest("s1", "Paper A", [
        {"claim": "good", "quote": "q", "verified": True},
        {"claim": "unverified", "quote": "q", "verified": False},
        {"claim": "ungrounded", "quote": "q", "verified": True, "grounded": False},
        {"claim": "", "quote": "q", "verified": True},
        {"claim": "no quote", "quote": "", "verified": True}])]
    got = fc.load_claims(d)
    assert [c["claim"] for c in got] == ["good"]
    assert got[0]["weight"] == round(0.8 * fc.EVIDENCE_WEIGHT["full_text"], 3)


def test_load_claims_counts_a_repeated_statement_of_one_source_once():
    """Loop 2 can read a source again and find the same sentence."""
    d = [digest("s1", "Paper A", [{"claim": "X is faster.", "quote": "q1", "verified": True}]),
         digest("s1", "Paper A", [{"claim": "x is  faster.", "quote": "q2", "verified": True}, {"claim": "Y is smaller.", "quote": "q3", "verified": True}])]
    assert [c["claim"] for c in fc.load_claims(d)] == ["X is faster.", "Y is smaller."]


def test_older_rows_without_an_evidence_level_count_as_full_text():
    d = [{"source_id": "s", "source_title": "T", "reliability": 0.5, "findings": [{"claim": "c", "quote": "q", "verified": True}]}]
    assert fc.load_claims(d)[0]["evidence_level"] == "full_text"


# --------------------------------------------------------------------------------------------- distinct docs, noisy-or, labels
def test_distinct_docs_keeps_the_strongest_item_per_document():
    items = [claim("a", "D1", 0.3), claim("a", "D1", 0.7), claim("a", "D2", 0.5)]
    best = {i["doc"]: i["weight"] for i in fc._distinct_docs(items)}
    assert best == {"D1": 0.7, "D2": 0.5}


def test_noisy_or_is_monotone_and_caps_each_weight():
    assert fc._noisy_or([]) == 0.0
    assert fc._noisy_or([claim("a", "D", 0.5)]) == 0.5
    assert fc._noisy_or([claim("a", "D", 0.5), claim("a", "E", 0.5)]) == 0.75
    assert fc._noisy_or([claim("a", "D", 2.0)]) == 0.95            # one source can never reach certainty


def cluster(text, members, support=None):
    return {"claim": text, "emb": np.zeros(2), "members": members, "support": members if support is None else support}


def sup(m, **kw):
    return {**m, "relation": "supports", "prob": 0.9, **kw}


def test_two_independent_documents_make_a_claim_supported():
    rows = fc.label_clusters([cluster("c", [], [sup(claim("c", "D1")), sup(claim("c", "D2"))])], {})
    assert rows[0]["label"] == "supported" and rows[0]["support_doc_count"] == 2 and rows[0]["contested"] is False


def test_one_document_is_never_enough_even_with_many_quotes():
    rows = fc.label_clusters([cluster("c", [], [sup(claim("c", "D1", 0.9)), sup(claim("c", "D1", 0.8))])], {})
    assert rows[0]["label"] == "unverified" and rows[0]["support_doc_count"] == 1 and rows[0]["confidence"] <= 0.5


def test_two_weak_documents_do_not_reach_the_evidence_minimum():
    weak = [sup(claim("c", "D1", 0.3, ev=0.5)), sup(claim("c", "D2", 0.3, ev=0.5))]          # evidence weight 0.5 + 0.5 < MIN_EVIDENCE
    assert fc.label_clusters([cluster("c", [], weak)], {})[0]["label"] == "unverified"


def test_a_claim_no_quote_supports_is_dropped_not_labelled():
    assert fc.label_clusters([cluster("drift", [claim("drift", "D1")], [])], {}) == []


def test_a_conflict_that_outweighs_the_support_makes_it_contradicted_and_a_weaker_one_only_contested():
    support = [sup(claim("c", "D1", 0.4)), sup(claim("c", "D2", 0.4))]
    strong = {0: [{**claim("not c", "D3", 0.9), "relation": "contradicts", "prob": 0.9}]}
    weak = {0: [{**claim("not c", "D3", 0.2), "relation": "contradicts", "prob": 0.9}]}
    r1 = fc.label_clusters([cluster("c", [], support)], strong)[0]
    r2 = fc.label_clusters([cluster("c", [], support)], weak)[0]
    assert r1["label"] == "contradicted" and r1["contra_doc_count"] == 1
    assert r2["label"] == "supported" and r2["contested"] is True
    assert {e["relation"] for e in r2["evidence"]} == {"supports", "contradicts"}


def test_evidence_rows_hold_only_plain_fields_for_the_database():
    row = fc.label_clusters([cluster("c", [], [sup(claim("c", "D1"), q_emb=np.zeros(3)), sup(claim("c", "D2"))])], {})[0]
    assert all(set(e) == {"source_id", "source_title", "quote", "relation", "reliability", "evidence_level", "prob", "via"} for e in row["evidence"])


# ------------------------------------------------------------------------------------------------------------ build_clusters
def test_clustering_asks_the_judge_only_in_the_gray_zone_and_never_for_the_same_document(monkeypatch):
    asked = []
    monkeypatch.setattr(fc, "judge_same_claim", lambda a, b: asked.append((a, b)) or True)
    claims = [claim("speed@a first", "D1", 0.9),            # strongest: representative
              claim("speed@b second", "D2", 0.8),           # same topic, other document, cosine 0.89: the judge decides
              claim("speed@b third", "D1", 0.7),            # same document as a member: no judge, no merge
              claim("memory@a other", "D3", 0.6)]           # other topic: own cluster
    clusters = fc.build_clusters(claims)
    assert asked == [("speed@a first", "speed@b second")]
    assert sorted(len(c["members"]) for c in clusters) == [1, 1, 2]


def test_near_identical_wording_merges_without_the_judge(monkeypatch):
    monkeypatch.setattr(fc, "judge_same_claim", lambda a, b: pytest.fail("the judge must not be asked"))
    clusters = fc.build_clusters([claim("speed@a one", "D1", 0.9), claim("speed@a two", "D2", 0.8)])
    assert len(clusters) == 1 and len(clusters[0]["members"]) == 2


def test_clustering_never_merges_when_the_judge_says_no(monkeypatch):
    monkeypatch.setattr(fc, "judge_same_claim", lambda a, b: False)
    assert len(fc.build_clusters([claim("speed@a a", "D1", 0.9), claim("speed@b b", "D2", 0.8)])) == 2


def test_clustering_result_does_not_depend_on_the_number_of_threads(monkeypatch):
    def fake_judge(a, b):
        time.sleep(0.01 * (len(a) % 3))                        # different answers arrive at different times
        return (len(a) + len(b)) % 2 == 0
    monkeypatch.setattr(fc, "judge_same_claim", fake_judge)
    claims = [claim(f"speed@{'ab'[i % 2]} claim number {i}", f"D{i}", 0.95 - i / 100) for i in range(14)]
    results = []
    for w in ("1", "4"):
        monkeypatch.setenv("STAGE4_WORKERS", w)
        results.append([[m["claim"] for m in c["members"]] for c in fc.build_clusters(list(claims))])
    assert results[0] == results[1]


def test_merge_budget_exhaustion_is_logged_and_stops_merging(monkeypatch, caplog):
    monkeypatch.setattr(fc, "MAX_MERGE_JUDGE", 1)
    monkeypatch.setattr(fc, "judge_same_claim", lambda a, b: True)
    claims = [claim("speed@a rep", "D0", 0.99)] + [claim(f"speed@b claim {i}", f"D{i + 1}", 0.9 - i / 100) for i in range(4)]
    with caplog.at_level(logging.WARNING, logger="apps.api.agents.stage4_factcheck"):
        clusters = fc.build_clusters(claims)
    assert any("merge judge budget" in r.message for r in caplog.records)
    assert len(clusters) >= 2


# ------------------------------------------------------------------------------------------------------------ verify_support
def test_support_uses_nli_first_then_the_judge_for_rejections(monkeypatch):
    probs = {"quote ok": {"entailment": 0.9, "contradiction": 0.0, "neutral": 0.1},
             "quote neutral": {"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0},
             "quote opposite": {"entailment": 0.0, "contradiction": 0.9, "neutral": 0.1}}
    monkeypatch.setattr(fc, "nli_probs", lambda pairs: [probs[q] for q, _ in pairs])
    asked = []
    monkeypatch.setattr(fc, "judge_support", lambda c, q: asked.append(q) or {"supports": True, "confidence": 0.9, "reason": ""})
    members = [claim("c", "D1", quote="quote ok"), claim("c", "D2", quote="quote neutral"), claim("c", "D3", quote="quote opposite")]
    out = fc.verify_support([{"claim": "c", "emb": np.zeros(2), "members": members}])
    assert [m["doc"] for m in out[0]["support"]] == ["D1", "D2"]            # D3 contradicts: not re-checked, not support
    assert asked == ["quote neutral"]


def test_a_low_confidence_or_failed_support_judge_does_not_count(monkeypatch):
    monkeypatch.setattr(fc, "nli_probs", lambda pairs: [{"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0}] * len(pairs))
    monkeypatch.setattr(fc, "judge_support", lambda c, q: {"supports": True, "confidence": 0.5, "reason": ""})
    out = fc.verify_support([{"claim": "c", "emb": np.zeros(2), "members": [claim("c", "D1")]}])
    assert out[0]["support"] == []


def test_support_budget_is_charged_in_order_and_logged(monkeypatch, caplog):
    monkeypatch.setattr(fc, "MAX_SUPPORT_JUDGE", 2)
    monkeypatch.setattr(fc, "nli_probs", lambda pairs: [{"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0}] * len(pairs))
    asked = []
    monkeypatch.setattr(fc, "judge_support", lambda c, q: asked.append(q) or {"supports": True, "confidence": 0.9, "reason": ""})
    clusters = [{"claim": f"c{i}", "emb": np.zeros(2), "members": [claim(f"c{i}", f"D{i}", quote=f"q{i}")]} for i in range(4)]
    with caplog.at_level(logging.WARNING, logger="apps.api.agents.stage4_factcheck"):
        out = fc.verify_support(clusters)
    assert sorted(asked) == ["q0", "q1"] and [bool(c["support"]) for c in out] == [True, True, False, False]
    assert any("support judge budget" in r.message for r in caplog.records)


# ----------------------------------------------------------------------------------------------------------------- detect
def make_cluster(text, docs_quotes):
    members = [sup(claim(text, d, quote=q)) for d, q in docs_quotes]
    c = cluster(text, [], members)
    c["emb"] = FakeEmbedder().encode([text])[0]
    return c


def two_clusters():
    return [make_cluster("speed@a 4-bit is faster", [("D1", "speed@a faster quote one"), ("D2", "speed@a faster quote two")]),
            make_cluster("speed@a 4-bit is slower", [("D3", "speed@a slower quote")])]


NLI_HIGH = lambda pairs: [{"contradiction": 0.95, "entailment": 0.0, "neutral": 0.05}] * len(pairs)       # noqa: E731


def test_a_conflict_needs_nli_and_the_judge_and_the_same_aspect(monkeypatch):
    monkeypatch.setattr(cd, "nli_probs", NLI_HIGH)
    monkeypatch.setattr(cd, "judge_conflict", lambda a, q, o: {"same_aspect": True, "conflicts": True, "confidence": 0.9, "reason": "opposite"})
    conflicts, disagreements = cd.detect(two_clusters())
    assert 0 in conflicts and conflicts[0][0]["relation"] == "contradicts" and "judge_reason" in conflicts[0][0]
    assert len(disagreements) == 1 and disagreements[0]["reason"] == "opposite"


def test_nli_alone_never_creates_a_conflict(monkeypatch):
    monkeypatch.setattr(cd, "nli_probs", lambda pairs: [{"contradiction": 1.0, "entailment": 0.0, "neutral": 0.0}] * len(pairs))
    monkeypatch.setattr(cd, "judge_conflict", lambda a, q, o: {"same_aspect": True, "conflicts": False, "confidence": 0.99, "reason": "both can be true"})
    assert cd.detect(two_clusters()) == ({}, [])


@pytest.mark.parametrize("verdict", [
    {"same_aspect": False, "conflicts": True, "confidence": 0.99, "reason": ""},          # different aspect
    {"same_aspect": True, "conflicts": True, "confidence": 0.5, "reason": ""},            # not confident
    {"same_aspect": False, "conflicts": False, "confidence": 0.0, "reason": "judge failed: x"}])    # fail closed
def test_only_a_confident_same_aspect_conflict_counts(monkeypatch, verdict):
    monkeypatch.setattr(cd, "nli_probs", NLI_HIGH)
    monkeypatch.setattr(cd, "judge_conflict", lambda a, q, o: verdict)
    assert cd.detect(two_clusters()) == ({}, [])


def test_a_document_that_supports_a_claim_cannot_contradict_it(monkeypatch):
    cs = two_clusters()
    cs[1]["support"][0]["doc"] = "D1"                      # D1 supports claim A, so its quote under B must not be used against A
    monkeypatch.setattr(cd, "nli_probs", NLI_HIGH)
    monkeypatch.setattr(cd, "judge_conflict", lambda a, q, o: {"same_aspect": True, "conflicts": True, "confidence": 0.9, "reason": "x"})
    conflicts, _ = cd.detect(cs)
    assert 0 not in conflicts


def test_detect_logs_when_the_conflict_judge_budget_cuts_pairs(monkeypatch, caplog):
    monkeypatch.setattr(cd, "MAX_JUDGE", 1)
    cs = two_clusters() + [make_cluster("speed@a 4-bit is the same", [("D4", "speed@a same quote")])]
    monkeypatch.setattr(cd, "nli_probs", NLI_HIGH)
    monkeypatch.setattr(cd, "judge_conflict", lambda a, q, o: {"same_aspect": False, "conflicts": False, "confidence": 0.0, "reason": ""})
    with caplog.at_level(logging.WARNING, logger="apps.api.agents.stage4_factcheck"):
        cd.detect(cs)
    assert any("conflict judge" in r.message for r in caplog.records)


def test_a_topic_gate_keeps_unrelated_quotes_away_from_the_judge(monkeypatch):
    cs = [make_cluster("speed@a 4-bit is faster", [("D1", "speed@a q"), ("D2", "speed@a q2")]),
          make_cluster("memory@a 4-bit uses less", [("D3", "memory@a q")])]
    monkeypatch.setattr(cd, "nli_probs", NLI_HIGH)
    monkeypatch.setattr(cd, "judge_conflict", lambda *a: pytest.fail("a different topic must never reach the judge"))
    assert cd.detect(cs) == ({}, [])


# ------------------------------------------------------------------------------------------------------------- near matches
def ncluster(text, doc, vec, weight=0.6):
    m = sup(claim(text, doc, weight))
    return {"claim": text, "emb": np.array(vec, dtype=np.float32) / np.linalg.norm(vec), "members": [m], "support": [m]}


def test_a_single_source_claim_with_a_close_variant_in_another_document_is_partially_supported(monkeypatch):
    asked = []
    monkeypatch.setattr(fc, "judge_near_match", lambda a, b, q: asked.append((a, b)) or True)
    cl = [ncluster("one", "D1", [1, 0.2]), ncluster("two", "D2", [1, 0.3])]
    rows = fc.label_clusters(fc.find_near_matches(cl), {})
    assert [r["label"] for r in rows] == ["partially_supported", "partially_supported"]
    assert rows[0]["support_doc_count"] == 1                                 # still ONE document supports the claim itself
    assert rows[0]["evidence"][-1]["relation"] == "near_match" and rows[0]["evidence"][-1]["near_claim"] == "two"
    assert rows[0]["confidence"] <= 0.6 and len(asked) == 2


def test_no_near_match_stays_unverified_and_a_failed_or_negative_judge_never_creates_one(monkeypatch):
    monkeypatch.setattr(fc, "judge_near_match", lambda a, b, q: False)
    cl = [ncluster("one", "D1", [1, 0.2]), ncluster("two", "D2", [1, 0.3])]
    assert [r["label"] for r in fc.label_clusters(fc.find_near_matches(cl), {})] == ["unverified", "unverified"]


def test_the_near_judge_is_not_asked_about_unrelated_claims_or_the_same_document_or_supported_claims(monkeypatch):
    monkeypatch.setattr(fc, "judge_near_match", lambda a, b, q: pytest.fail("must not be asked"))
    unrelated = [ncluster("one", "D1", [1, 0]), ncluster("two", "D2", [0, 1])]
    fc.find_near_matches(unrelated)
    same_doc = [ncluster("one", "D1", [1, 0.2]), ncluster("two", "D1", [1, 0.3])]
    fc.find_near_matches(same_doc)
    already = ncluster("one", "D1", [1, 0.2])
    already["support"].append(sup(claim("one", "D2")))                      # two documents: that is "supported", not a near match
    fc.find_near_matches([already])


def test_supported_and_contradicted_win_over_a_near_match(monkeypatch):
    monkeypatch.setattr(fc, "judge_near_match", lambda a, b, q: True)
    c = ncluster("one", "D1", [1, 0.2])
    c["support"].append(sup(claim("one", "D2")))
    c["near"] = {**claim("x", "D3"), "relation": "near_match", "via": "near_judge", "near_claim": "x", "prob": 0.0}
    assert fc.label_clusters([c], {})[0]["label"] == "supported"
    d = ncluster("one", "D1", [1, 0.2])
    d["near"] = c["near"]
    strong = {0: [{**claim("not one", "D4", 0.9), "relation": "contradicts", "prob": 0.9}]}
    assert fc.label_clusters([d], strong)[0]["label"] == "contradicted"


def test_near_budget_is_charged_in_order_and_logged(monkeypatch, caplog):
    monkeypatch.setattr(fc, "MAX_NEAR_JUDGE", 1)
    asked = []
    monkeypatch.setattr(fc, "judge_near_match", lambda a, b, q: asked.append(a) or True)
    cl = [ncluster("one", "D1", [1, 0.2]), ncluster("two", "D2", [1, 0.3])]
    with caplog.at_level(logging.WARNING, logger="apps.api.agents.stage4_factcheck"):
        fc.find_near_matches(cl)
    assert asked == ["one"] and "near-match judge budget" in caplog.text


def test_near_matching_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(fc, "NEAR_ON", False)
    monkeypatch.setattr(fc, "judge_near_match", lambda *a: pytest.fail("off means off"))
    fc.find_near_matches([ncluster("one", "D1", [1, 0.2]), ncluster("two", "D2", [1, 0.3])])


def test_a_near_yes_without_a_named_shared_point_does_not_count(monkeypatch):
    monkeypatch.setattr(judge, "squeezer_json", lambda p, **_: {"near": True, "shared_point": "none", "reason": "x"})
    assert judge.judge_near_match("a", "b", "q") is False
    monkeypatch.setattr(judge, "squeezer_json", lambda p, **_: {"near": True, "shared_point": "MoE activates a subset of experts", "reason": "x"})
    assert judge.judge_near_match("a", "b", "q") is True


# ----------------------------------------------------------------------------------------------------------- judges + cache
def test_every_judge_fails_closed(monkeypatch):
    def boom(prompt, **_):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(judge, "squeezer_json", boom)
    assert judge.judge_conflict("a", "q", "b")["conflicts"] is False
    assert judge.judge_support("a", "q")["supports"] is False
    assert judge.judge_same_claim("a", "b") is False
    assert judge.judge_near_match("a", "b", "q") is False


def test_judge_replies_are_cached_and_failures_are_not(monkeypatch):
    monkeypatch.setenv("STAGE4_CACHE", "true")
    calls = []
    replies = iter([RuntimeError("down"), {"same": True}, {"same": False}])

    def fake(prompt, **_):
        calls.append(prompt)
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(judge, "squeezer_json", fake)
    assert judge.judge_same_claim("a", "b") is False            # failed: closed, not cached
    assert judge.judge_same_claim("a", "b") is True             # asked again, answered, cached
    assert judge.judge_same_claim("a", "b") is True             # from the cache: no third call
    assert len(calls) == 2


def test_run_parallel_returns_results_in_input_order():
    def slow(i):
        time.sleep(0.02 * (5 - i))
        return i
    assert judge.run_parallel(slow, [(i,) for i in range(5)]) == [0, 1, 2, 3, 4]


def test_nli_answers_are_cached_so_a_repeated_run_costs_no_cpu(monkeypatch, tmp_path):
    monkeypatch.setenv("NLI_CACHE", "true")
    monkeypatch.setenv("NLI_CACHE_DIR", str(tmp_path / "nli"))
    predicted = []

    class FakeNli:
        class config:
            id2label = {0: "contradiction", 1: "entailment", 2: "neutral"}

        def predict(self, pairs, batch_size=16):
            predicted.extend(pairs)
            return np.array([[0.1, 0.8, 0.1] for _ in pairs])
    monkeypatch.setattr(common, "_model", lambda: FakeNli())
    first = common.nli_probs([("a quote", "a claim"), ("b quote", "b claim")])
    assert first[0]["entailment"] == pytest.approx(0.8) and len(predicted) == 2
    again = common.nli_probs([("b quote", "b claim"), ("c quote", "c claim"), ("a  quote", "a claim")])      # b and a (cleaned) are cached
    assert [round(x["entailment"], 2) for x in again] == [0.8, 0.8, 0.8]
    assert len(predicted) == 3 and predicted[-1] == ("c quote", "c claim")                                 # only the new pair reached the model
    monkeypatch.setenv("NLI_CACHE", "false")
    common.nli_probs([("a quote", "a claim")])
    assert len(predicted) == 4                                                                             # switched off: always computed


# --------------------------------------------------------------------------------------------------------------- common
def test_doc_key_counts_the_same_document_found_as_web_page_and_paper_once():
    assert common.doc_key("Mamba: Linear-Time Sequence Modeling | arXiv", "web1") == common.doc_key("Mamba: Linear-Time Sequence Modeling", "paper1")
    assert common.doc_key(None, "id9") == "id9"


def test_clean_text_normalises_unicode_noise():
    assert common.clean_text("4‑bit  model  it’s") == "4-bit model it's"


# ------------------------------------------------------------------------------------------ reuse of Stage 3, circuit breaker
def test_a_quote_the_stage3_judge_already_accepted_needs_no_nli_and_no_llm_call(monkeypatch):
    monkeypatch.setattr(fc, "nli_probs", lambda pairs: [{"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0}] * len(pairs))
    monkeypatch.setattr(fc, "judge_support", lambda c, q: pytest.fail("the Groq judge must not be asked"))
    digests = [digest("s1", "Paper A", [{"claim": "c", "quote": "q", "verified": True, "judge": {"0": {"final": "partial", "quote_supports_claim": "yes"}}}])]
    claims = fc.load_claims(digests)
    assert claims[0]["stage3_support"] is True
    out = fc.verify_support([{"claim": "c", "emb": np.zeros(2), "members": claims}])
    assert out[0]["support"][0]["via"] == "stage3_judge"
    row = fc.label_clusters(out, {})[0]
    assert row["label"] == "unverified" and row["support_doc_count"] == 1       # one document is still not "supported"
    assert row["evidence"][0]["via"] == "stage3_judge"


def test_only_a_stage3_yes_counts_not_partial_or_no():
    for verdict, expected in (("yes", True), ("partial", False), ("no", False), (None, False)):
        f = {"claim": "c", "quote": "q", "verified": True, "judge": {"0": {"quote_supports_claim": verdict}}}
        assert fc._stage3_supports(f) is expected
    assert fc._stage3_supports({"claim": "c", "quote": "q", "verified": True}) is False


def test_the_judge_stops_asking_after_a_daily_limit_and_fails_closed_fast(monkeypatch):
    class GroqRateLimitExhausted(Exception):
        pass
    calls = []

    def limited(prompt, **_):
        calls.append(prompt)
        raise GroqRateLimitExhausted("all 7 Groq key(s) are rate limited for 900s")
    monkeypatch.setattr(judge, "squeezer_json", limited)
    judge.reset_breaker()
    s0 = judge.stats()
    assert judge.judge_same_claim("a", "b") is False
    assert judge.judge_same_claim("c", "d") is False                 # not even tried
    assert judge.judge_support("c", "q")["supports"] is False
    assert len(calls) == 1
    s1 = judge.stats()
    assert s1["failures"] - s0["failures"] == 1 and s1["skipped"] - s0["skipped"] == 2
    judge.reset_breaker()


def test_a_short_pool_wide_limit_is_waited_out_and_the_answer_is_not_lost(monkeypatch):
    slept = []
    monkeypatch.setattr(judge.time, "sleep", lambda s: slept.append(s))
    replies = iter([RuntimeError("all 7 Groq key(s) are rate limited for 124s"), {"same": True}])

    def flaky(prompt, **_):
        r = next(replies)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(judge, "squeezer_json", flaky)
    judge.reset_breaker()
    s0 = judge.stats()
    assert judge.judge_same_claim("a", "b") is True
    s1 = judge.stats()
    assert slept == [125.0] and s1["waits"] - s0["waits"] == 1 and s1["failures"] == s0["failures"]


def test_the_wait_is_limited_in_time_and_in_number_and_then_the_breaker_opens(monkeypatch):
    slept = []
    monkeypatch.setattr(judge.time, "sleep", lambda s: slept.append(s))
    calls = []

    def limited(prompt, **_):
        calls.append(prompt)
        raise RuntimeError("all 7 Groq key(s) are rate limited for 100s")
    monkeypatch.setattr(judge, "squeezer_json", limited)
    judge.reset_breaker()
    assert judge.judge_same_claim("a", "b") is False
    assert len(calls) == 1 + judge.RATE_RETRIES and len(slept) == judge.RATE_RETRIES          # waited, asked again, gave up
    assert judge.judge_same_claim("c", "d") is False and len(calls) == 1 + judge.RATE_RETRIES   # breaker open: not asked
    judge.reset_breaker()
    slept.clear()
    monkeypatch.setattr(judge, "squeezer_json", lambda p, **_: (_ for _ in ()).throw(RuntimeError("all 7 Groq key(s) are rate limited for 900s")))
    judge.judge_same_claim("e", "f")
    assert slept == []                                                  # a daily-size limit is never waited for
    judge.reset_breaker()


def test_an_ordinary_failure_does_not_trip_the_breaker(monkeypatch):
    monkeypatch.setattr(judge, "squeezer_json", lambda p, **_: (_ for _ in ()).throw(ValueError("bad json")))
    judge.reset_breaker()
    judge.judge_same_claim("a", "b")
    judge.judge_same_claim("c", "d")
    assert judge.stats()["skipped"] == judge.stats()["skipped"]       # unchanged by these two
    monkeypatch.setattr(judge, "squeezer_json", lambda p, **_: {"same": True})
    assert judge.judge_same_claim("e", "f") is True


# ------------------------------------------------------------------------------------- the conflict judge needs two readings
def test_a_conflict_needs_the_confirming_second_reading(monkeypatch):
    replies = {"first": {"same_aspect": True, "conflicts": True, "confidence": 0.9, "reason": "opposite"}}
    calls = []

    def fake(prompt, **_):
        calls.append(prompt)
        return replies["first"] if "DIRECTLY CONTRADICT" in prompt and "second reader" not in prompt else replies["second"]
    monkeypatch.setattr(judge, "squeezer_json", fake)
    replies["second"] = {"both_can_be_true": False, "reason": "plainly opposite"}
    assert judge.judge_conflict("a", "q", "b")["conflicts"] is True and len(calls) == 2
    replies["second"] = {"both_can_be_true": True, "reason": "hedged"}
    v = judge.judge_conflict("a2", "q", "b")
    assert v["conflicts"] is False and v["reason"].startswith("not confirmed")
    replies["second"] = {"reason": "no field"}                                    # a missing answer means "can be reconciled"
    assert judge.judge_conflict("a3", "q", "b")["conflicts"] is False


def test_no_second_reading_when_the_first_sees_no_conflict_and_a_failing_second_fails_closed(monkeypatch):
    seq = iter([{"same_aspect": True, "conflicts": False, "confidence": 0.9, "reason": ""}])
    monkeypatch.setattr(judge, "squeezer_json", lambda p, **_: next(seq))
    assert judge.judge_conflict("a", "q", "b")["conflicts"] is False                 # a second call would raise StopIteration
    answers = iter([{"same_aspect": True, "conflicts": True, "confidence": 0.9, "reason": ""}, RuntimeError("down")])

    def second_fails(p, **_):
        r = next(answers)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(judge, "squeezer_json", second_fails)
    assert judge.judge_conflict("a4", "q", "b")["conflicts"] is False


# ------------------------------------------------------------------------------------------------------------ the graph node
def test_the_node_does_nothing_unless_switched_on(monkeypatch):
    from apps.api.graph.nodes import factcheck_node as node
    monkeypatch.delenv("FACTCHECK", raising=False)
    monkeypatch.setattr(node, "run_factcheck", lambda *a: pytest.fail("Stage 4 must not run"))
    assert node.factcheck_node(None) == {}


def fake_state():
    from types import SimpleNamespace
    sqs = [SimpleNamespace(id="s1", main_topic="T1"), SimpleNamespace(id="s2", main_topic="T2")]
    return SimpleNamespace(task_plan=SimpleNamespace(query_id="q1", sub_questions=sqs))


def test_the_node_returns_claims_and_summary_and_survives_a_final_failure(monkeypatch):
    from apps.api.graph.nodes import factcheck_node as node
    monkeypatch.setenv("FACTCHECK", "true")
    monkeypatch.setattr(node, "run_factcheck", lambda q, sqs: ([{"label": "supported"}, {"label": "unverified"}], {"s1": {"supported": 1}}))
    out = node.factcheck_node(fake_state())
    assert len(out["fact_claims"]) == 2 and out["fact_summary"] == {"s1": {"supported": 1}}
    monkeypatch.setattr(node, "run_factcheck", lambda q, sqs: (_ for _ in ()).throw(ConnectionError("database down")))
    out = node.factcheck_node(fake_state())
    assert "ConnectionError" in out["fact_summary"]["error"] and "fact_claims" not in out


def test_one_failing_sub_question_does_not_stop_the_others_and_nothing_is_written_for_it(monkeypatch):
    from apps.api.graph.nodes import factcheck_node as node
    written = {}

    def check(query_id, sq, report):
        if sq.id == "s1":
            raise RuntimeError("model error")
        return [{"label": "supported", "claim": "c"}], [], {"supported": 1, "disagreements": 0}
    monkeypatch.setattr(node, "_check_sub_question", check)
    monkeypatch.setattr(node.db_service, "write_fact_claims", lambda q, rows: written.update(claims=rows))
    monkeypatch.setattr(node.db_service, "write_contradictions", lambda q, rows: written.update(contra=rows))
    claims, summary = node.run_factcheck("q1", fake_state().task_plan.sub_questions)
    assert "RuntimeError" in summary["s1"]["error"] and summary["s2"]["supported"] == 1
    assert written == {"claims": [{"label": "supported", "claim": "c"}], "contra": []}


# --------------------------------------------------------------------------------------------------- the stage in the run manager
class GraphWithFactcheck:
    def stream(self, state, stream_mode):
        from types import SimpleNamespace
        sq = SimpleNamespace(main_topic="What are SSMs?", queries=["a"])
        yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[sq], domain_anchor="")}}
        yield {"paper_retrieval": {"paper_results": []}}
        yield {"web_search": {"web_sources": []}}
        yield {"summarizer": {"digests": [1], "coverage": {"a": {"sufficient": True}}}}
        yield {"factcheck": {"fact_claims": [{"label": "supported", "contested": False}, {"label": "contradicted", "contested": False},
                                              {"label": "unverified", "contested": False}],
                             "fact_summary": {"a": {"disagreements": 1}}}}


def run_to_end(graph, monkeypatch, enabled):
    from apps.api.services import run_manager as rm
    monkeypatch.setenv("FACTCHECK", "true" if enabled else "false")
    manager = rm.RunManager(graph_factory=lambda: graph, max_workers=1)
    try:
        rec = manager.submit("How do state space models compare with transformers in training efficiency?")
        for _ in range(250):
            if rec.finished:
                break
            time.sleep(0.02)
        assert rec.status == "completed", rec.error
        return rec
    finally:
        manager.shutdown()


def test_the_factcheck_stage_runs_and_reports_its_result_when_switched_on(monkeypatch):
    rec = run_to_end(GraphWithFactcheck(), monkeypatch, True)
    assert rec.stages == {"planner": "completed", "retrieval": "completed", "summarizer": "completed", "factcheck": "completed", "report": "not_run"}
    started = [e for e in rec.events if e["stage"] == "factcheck"]
    assert [e["event"] for e in started] == ["stage_started", "stage_completed"]
    assert {k: v for k, v in started[1]["data"].items() if k != "groq"} == {"claims": 3, "subQuestions": 1, "failedSubQuestions": 0, "supported": 1, "partially_supported": 0, "unverified": 1, "contradicted": 1, "contested": 0, "disagreements": 1, "judgeFailures": 0, "judgeWaits": 0}
    assert rec.events[-1]["data"]["stagesNotRun"] == ["report"]


def test_the_factcheck_stage_is_not_run_when_switched_off(monkeypatch):
    rec = run_to_end(GraphWithFactcheck(), monkeypatch, False)
    assert rec.stages["factcheck"] == "not_run" and not [e for e in rec.events if e["stage"] == "factcheck"]
    assert rec.events[-1]["data"]["stagesNotRun"] == ["factcheck", "report"]


def test_a_failed_factcheck_fails_the_stage_but_not_the_run(monkeypatch):
    class G(GraphWithFactcheck):
        def stream(self, state, stream_mode):
            for chunk in super().stream(state, stream_mode):
                yield chunk if "factcheck" not in chunk else {"factcheck": {"fact_summary": {"error": "ConnectionError: database down"}}}
    rec = run_to_end(G(), monkeypatch, True)
    assert rec.status == "completed" and rec.stages["factcheck"] == "failed"
    assert [e for e in rec.events if e["stage"] == "factcheck"][-1]["data"].get("error") == "ConnectionError: database down"
