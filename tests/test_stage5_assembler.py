"""Stage 5 assembler, report node and the stored-run script. All offline: the LLM, the sentence check, the NLI model and the judge are fakes, the
inputs are hand-made dicts in the shape of loader.load_inputs, and the database is a fake function. Nothing reaches Groq, a model or the network."""
import importlib.util
import json
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api.agents.stage5_report import assembler, grounding, writer
from apps.api.graph.nodes import report_node
from apps.api.services import progress

ROOT = Path(__file__).resolve().parent.parent
_ENV = ("STAGE5", "STAGE5_MODEL", "STAGE5_RETRIES", "STAGE5_CACHE", "STAGE5_CACHE_DIR", "STAGE5_MAX_PER_SOURCE", "STAGE5_SINGLE_NEEDS_STRONG",
        "STAGE5_SCOPE_CHECK", "STAGE5_MAX_SINGLE_PER_SECTION", "STAGE5_WORKERS")


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)           # the real .env may set some of them
    monkeypatch.setenv("STAGE5_CACHE", "false")
    writer.default_rate.reset()
    yield
    writer.default_rate.reset()


# ------------------------------------------------------------------------------------------------------------ hand-made inputs
TEXT_C1 = "Vision transformers reach 88.5% top-1 accuracy on ImageNet when pre-trained on large data."
TEXT_C2 = "Transformers need more pre-training data than CNNs."
TEXT_C3 = "Hybrid models converge faster in early training."
TEXT_C4 = "Mixed precision halves the memory of the model."
TEXT_C5 = "Transformers are cheaper to train than CNNs."
TEXT_C6 = "Pruning reduces inference cost by 30 percent."
TEXT_C7 = "Edge devices need at least 8 GB of memory."


def ev(sid, title, quote, relation="supports", level="full_text", **kw):
    return {"source_id": sid, "source_title": title, "quote": quote, "relation": relation, "reliability": 0.8, "evidence_level": level, "prob": 0.9, **kw}


def row(sq, text, label, evidence, contested=False, conf=0.5, supports=None, contra=0):
    return {"claim": text, "label": label, "confidence": conf, "support_doc_count": supports if supports is not None else
            len({e["source_title"] for e in evidence if e["relation"] == "supports"}), "contra_doc_count": contra, "contested": contested,
            "evidence": evidence, "sub_question_id": sq}


def cov(**kw):
    base = {"present": True, "sufficient": True, "source_count": 5, "full_text_source_count": 3, "uncovered_details": [], "uncovered_aspects": [],
            "unjudged_aspects": [], "known_gaps": [], "covered_by_synthesis": [], "digest_failures": 0, "fallback_reason": None}
    return {**base, **kw}


SOURCES = {
    "s_a": {"kind": "paper", "title": "Vision Transformers at Scale", "authors": ["A. Author", "B. Writer"], "year": 2021, "venue": "ICLR", "doi": "10.1/vit",
            "url": "https://doi.org/10.1/vit", "evidence_level": "full_text"},
    "s_a2": {"kind": "paper", "title": "Vision Transformers at Scale", "authors": [], "year": None, "venue": None, "doi": None, "url": None, "evidence_level": "abstract"},
    "s_b": {"kind": "paper", "title": "Convolutional Networks Revisited", "authors": ["C. Coder"], "year": 2022, "venue": "CVPR", "doi": None,
            "url": "https://arxiv.org/abs/2201.1", "evidence_level": "full_text"},
    "s_c": {"kind": "web", "title": "A Transformer Tutorial | Some Blog", "authors": [], "url": "https://www.someblog.org/tutorial", "published": "2023-05-01",
            "evidence_level": "web_snippet"},
    "s_d": {"kind": "paper", "title": "Data Efficiency of CNNs", "authors": ["D. Dee"], "year": 2020, "venue": None, "doi": None, "url": "https://arxiv.org/abs/2001.2",
            "evidence_level": "full_text"},
    "s_e": {"kind": "paper", "title": "Training Costs of Transformers", "authors": ["E. Eee", "F. Eff", "G. Gee", "H. Aitch"], "year": 2023, "venue": "NeurIPS",
            "doi": "10.2/cost", "url": "https://doi.org/10.2/cost", "evidence_level": "full_text"},
}


def make_inputs():
    s1 = [
        row("sq1", TEXT_C1, "supported", [ev("s_a", "Vision Transformers at Scale", "ViT reaches 88.5% top-1 on ImageNet."),
                                           ev("s_b", "Convolutional Networks Revisited", "Pre-trained ViT attains 88.5% top-1 accuracy.")], conf=0.9),
        row("sq1", TEXT_C2, "partially_supported", [ev("s_d", "Data Efficiency of CNNs", "CNNs need less pre-training data than transformers."),
                                                    ev("s_c", "A Transformer Tutorial | Some Blog", "Large datasets matter more for transformers.", "near_match",
                                                       "web_snippet", near_claim="Large datasets matter more for transformers.")], conf=0.6),
        row("sq1", TEXT_C3, "unverified", [ev("s_e", "Training Costs of Transformers", "Hybrid models converge faster in the first epochs.")], conf=0.5),
        row("sq1", TEXT_C4, "unverified", [ev("s_d", "Data Efficiency of CNNs", "Mixed precision halves memory.", level="abstract")], conf=0.4),
    ]
    s2 = [
        row("sq2", TEXT_C5, "contradicted", [ev("s_e", "Training Costs of Transformers", "Transformers train for fewer GPU hours.", level="abstract"),
                                              ev("s_b", "Convolutional Networks Revisited", "CNNs need fewer GPU hours than transformers.", "contradicts")],
            conf=0.4, contra=1),
        row("sq2", TEXT_C6, "unverified", [ev("s_a2", "Vision Transformers at Scale", "Pruning removes 30% of the cost.", level="abstract", via="stage3_judge")], conf=0.5),
    ]
    s3 = [row("sq3", TEXT_C7, "unverified", [ev("s_c", "A Transformer Tutorial | Some Blog", "Edge devices have little memory.", level="web_snippet")], conf=0.3)]
    contradiction = {"claim_a": TEXT_C5, "claim_b": "CNNs need fewer GPU hours than transformers.", "source_a_title": "Training Costs of Transformers",
                     "source_b_title": "Convolutional Networks Revisited", "quote_a": "Transformers train for fewer GPU hours.",
                     "quote_b": "CNNs need fewer GPU hours than transformers.", "prob": 0.8, "reason": "They give opposite results for training time.",
                     "sub_question_id": "sq2"}
    return {"query_id": "q1", "question": "How do vision transformers compare with CNNs?", "created_at": "2026-11-10T12:00:00+00:00",
            "domain_context": "Deep learning for image classification.", "domain_anchor": "deep learning", "fact_ran": True, "fact_error": None,
            "status_hints": {"origin": "db", "found": True, "fact_failed_sub_questions": [], "coverage_missing": [], "no_claims_sub_questions": [],
                             "judge_failures": None, "sources_without_metadata": 0},
            "sub_questions": [
                {"id": "sq1", "title": "How do vision transformers compare with CNNs on accuracy?", "detail_questions": ["What accuracy do they reach?"],
                 "coverage": cov(), "claims": s1, "contradictions": [], "fact_summary": None, "fact_error": None},
                {"id": "sq2", "title": "How do the two compare on cost?", "detail_questions": ["What does training cost?"],
                 "coverage": cov(), "claims": s2, "contradictions": [contradiction], "fact_summary": None, "fact_error": None},
                {"id": "sq3", "title": "Which hardware is needed?", "detail_questions": ["What GPUs are required?"],
                 "coverage": cov(sufficient=False, uncovered_details=["What GPUs are required?"], known_gaps=["Memory needs of edge devices"], digest_failures=1),
                 "claims": s3, "contradictions": [], "fact_summary": None, "fact_error": None}],
            "sources": SOURCES}


def empty_inputs(**kw):
    inputs = make_inputs()
    for sq in inputs["sub_questions"]:
        sq["claims"], sq["contradictions"] = [], []
    inputs.update({"fact_ran": False, **kw})
    return inputs


# ------------------------------------------------------------------------------------------------------------ fakes
def ok_check(text, ids, job):
    return []


def parse_jobs(messages):
    """{job_id: {"tier", "claims": [(id, text)], "near": text|None}} read back from the rendered write prompt."""
    jobs, cur = {}, None
    for line in messages[1]["content"].splitlines():
        m = re.match(r"JOB (\S+) \(tier: (\w+)\)", line)
        if m:
            cur = m.group(1)
            jobs[cur] = {"tier": m.group(2), "claims": [], "near": None}
            continue
        m = re.match(r"\s+claim (\S+): (.*)", line)
        if m and cur:
            jobs[cur]["claims"].append((m.group(1), m.group(2)))
        m = re.match(r'\s+related wording from another source: "(.*)"', line)
        if m and cur:
            jobs[cur]["near"] = m.group(1)
    return jobs


def job_sentence(job_id, job):
    body = " and ".join(t.rstrip(".") for _, t in job["claims"])
    text = {"supported": f"Two sources report that {body}.", "single": f"One study reports that {body}.",
            "partly": f"One source reports that {body}, while another makes a related point that {(job['near'] or 'something close').rstrip('.')}."}[job["tier"]]
    return {"job_id": job_id, "text": text, "claim_ids": [cid for cid, _ in job["claims"]]}


class FakeLLM:
    """Writes a sentence for every job, and a summary / conclusion made of copies of numbered sentences. Records every call."""

    def __init__(self, summary_pick=(1, 2, 3), bad_summary=None, fail=None):
        self.calls, self.summary_pick, self.bad_summary, self.fail = [], list(summary_pick), bad_summary, fail

    def __call__(self, messages, response_format, purpose):
        self.calls.append(purpose)
        if self.fail:
            raise self.fail
        if purpose == "stage5_write":
            return {"sentences": [job_sentence(i, j) for i, j in parse_jobs(messages).items()]}, {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
        numbered = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d+)\. \[\w+\] (.*)$", messages[1]["content"], re.M)}
        is_conclusion = "You write the conclusion" in messages[0]["content"]
        if self.bad_summary and not is_conclusion:
            return {"sentences": [{"text": self.bad_summary, "from_sentences": [1]}] * 3}
        picks = self.summary_pick if not is_conclusion else sorted(numbered)[-3:]
        return {"sentences": [{"text": numbered[n], "from_sentences": [n]} for n in picks if n in numbered]}, {"total_tokens": 50}

    def purposes(self, name):
        return [p for p in self.calls if p == name]


def build(inputs=None, llm=None, **kw):
    llm = llm if llm is not None else FakeLLM()
    kw.setdefault("check", ok_check)
    kw.setdefault("cache", False)
    kw.setdefault("workers", 1)
    return assembler.build_report(inputs or make_inputs(), llm=llm, **kw)


def all_text_fields(report):
    """Every text the renderer shows, for the 'no [n] in the text' check."""
    texts = list(report["introduction"]) + list(report["limitations"])
    texts += [s["text"] for s in report["overview"]["summary"] + report["conclusion"]]
    for sec in report["sections"]:
        texts += [s["text"] for s in sec["sentences"]] + list(sec["gaps"]) + [sec["title"]]
        for d in sec["disagreements"]:
            texts += [d["claimA"], d["claimB"], d["sideA"]["quote"], d["sideB"]["quote"], d["note"]]
    return texts


# ------------------------------------------------------------------------------------------------------------ the full build
def test_full_build_has_every_tier_and_a_gap_section():
    llm = FakeLLM()
    result = build(llm=llm)
    report = result["report"]
    assert result["status"] == "completed" and report["status"] == "completed" and result["warnings"] == []
    assert [s["title"] for s in report["sections"]] == [sq["title"] for sq in make_inputs()["sub_questions"]]
    s1, s2, s3 = report["sections"]
    assert [s["tier"] for s in s1["sentences"]] == ["supported", "partly", "single"]
    assert all(s["origin"] == "llm" for s in s1["sentences"])
    assert s1["sentences"][0]["text"].startswith("Two sources report that")
    assert s1["sentences"][2]["text"].startswith("One study reports that")
    assert any("1 claim not used because" in g and "abstract or a web snippet" in g for g in s1["gaps"])       # C4 filtered: weak evidence
    # the disputed claim is never prose; it is a "Sources disagree" pair with both sides cited
    assert [s["tier"] for s in s2["sentences"]] == ["single"] and "Pruning" in s2["sentences"][0]["text"]
    assert all(TEXT_C5 not in s["text"] for s in s2["sentences"])
    assert len(s2["disagreements"]) == 1
    d = s2["disagreements"][0]
    assert d["claimA"] == TEXT_C5 and d["sideA"]["ref"] and d["sideB"]["ref"] and d["sideA"]["ref"] != d["sideB"]["ref"]
    assert "disagree" in d["note"] and "not reviewed" in d["note"]
    # a section with no eligible claim says why
    assert s3["sentences"] == [] and s3["disagreements"] == []
    gap_text = " ".join(s3["gaps"])
    assert "What GPUs are required?" in gap_text and "Memory needs of edge devices" in gap_text and "1 source could not be summarised" in gap_text
    assert "No claim in this section met the conditions" in gap_text and "1 claim not used" in gap_text
    # the standing caveat and the counts
    assert any("compares only the most similar pairs" in x and "automatic" in x for x in report["limitations"])
    assert report["overview"]["counts"]["supported"] == 1 and report["overview"]["counts"]["disputed"] == 1
    assert report["overview"]["counts"]["filtered"] == 2
    assert any("No eligible claim was found for: Which hardware is needed?" in x for x in report["limitations"])
    # LLM use: one write call per section with jobs, then the summary and the conclusion
    assert llm.purposes("stage5_write") == ["stage5_write"] * 2 and llm.purposes("stage5_summary") and "stage5_summary" in llm.calls
    st = result["stats"]
    assert st["calls"] == len(llm.calls) and st["tokens"] > 0 and st["sentences"]["fallback"] == 0 and st["sentences"]["llm"] == 4
    assert st["claims"] == {"total": 7, "supported": 1, "partly": 1, "single": 2, "disputed": 1, "filtered": 2}
    assert st["filtered"] == {"weak_evidence": 2}
    assert result["model"] == "openai/gpt-oss-120b" and result["template_version"] == "s5-v1"
    assert report["generatedAt"] and report["stats"] == st and report["warnings"] == []


def test_summary_and_conclusion_come_from_the_body_and_keep_labels():
    result = build()
    report = result["report"]
    body = [s["text"] for sec in report["sections"] for s in sec["sentences"]]
    assert len(report["overview"]["summary"]) == 3 and len(report["conclusion"]) == 3
    for s in report["overview"]["summary"] + report["conclusion"]:
        assert s["text"] in body and s["claimIds"] and s["refs"]
    assert sorted(s["tier"] for s in report["overview"]["summary"]) == ["partly", "single", "supported"]   # the tier of the sentence it copies
    claim_tier = {c["claimIds"][0]: c["tier"] for sec in report["sections"] for c in sec["sentences"]}
    for s in report["overview"]["summary"]:
        assert claim_tier[s["claimIds"][0]] == s["tier"]


def test_no_citation_marker_in_any_text_field_and_markers_only_in_markdown():
    result = build()
    for text in all_text_fields(result["report"]):
        assert not re.search(r"\[\s*\d+", text), text
    assert re.search(r"report that .* \[\d+(, \d+)*\]\.", result["markdown"])


def test_references_are_numbered_by_first_citation_in_render_order_and_deduplicated():
    llm = FakeLLM(summary_pick=(3, 1, 2))                      # the summary cites the single-source sentence (Training Costs) FIRST
    result = build(llm=llm)
    report = result["report"]
    refs = report["references"]
    assert [r["number"] for r in refs] == list(range(1, len(refs) + 1))
    first_s = report["overview"]["summary"][0]
    assert first_s["refs"][0] == 1                                              # numbered from the summary (it comes first), not from section 1
    assert first_s["refs"] == list(range(1, len(first_s["refs"]) + 1))
    titles = [r["title"] for r in refs]
    assert titles.count("Vision Transformers at Scale") == 1                   # s_a and s_a2 are one document
    vit = next(r for r in refs if r["title"] == "Vision Transformers at Scale")
    assert sorted(vit["sourceIds"]) == ["s_a", "s_a2"] and vit["authors"] == ["A. Author", "B. Writer"] and vit["year"] == 2021
    cited = {n for s in report["overview"]["summary"] + report["conclusion"] for n in s["refs"]}
    for sec in report["sections"]:
        cited |= {n for s in sec["sentences"] for n in s["refs"]}
        for d in sec["disagreements"]:
            cited |= {d["sideA"]["ref"], d["sideB"]["ref"]}
    assert cited == {r["number"] for r in refs}                                # every reference is cited, every cited number exists
    # a partly sentence cites both documents; a disagreement cites both sides
    partly = report["sections"][0]["sentences"][1]
    assert len(partly["refs"]) == 2
    web = next(r for r in refs if r["kind"] == "web")
    assert web["url"] == "https://www.someblog.org/tutorial" and "someblog.org" in web["text"] and "accessed 2026-11-10" in web["text"]


def test_markdown_structure_order_legend_and_tier_labels():
    md = build()["markdown"]
    heads = [h for h in re.findall(r"^#{1,2} (.+)$", md, re.M)]
    assert heads[0].startswith("How do vision transformers compare")
    order = ["Research Overview and Executive Summary", "Introduction", "Topic-wise Research Findings", "Limitations and Evidence Gaps", "Conclusion", "References"]
    assert [h for h in heads if h in order] == order
    assert "single-source findings are attributed to one document and are not confirmed" in md
    assert "*(one source, not confirmed)*" in md and "*(partly supported)*" in md
    assert "#### Sources disagree" in md and "**Sources disagree on:**" in md and "#### Evidence gaps" in md
    assert "### 1. How do vision transformers compare with CNNs on accuracy?" in md and "### 3. Which hardware is needed?" in md
    assert re.search(r"^\[1\] ", md, re.M) and "[Some Blog]" not in md
    assert "is false" not in md


def test_render_markdown_works_from_the_stored_report_dict_alone():
    result = build()
    stored = json.loads(json.dumps(result["report"]))
    assert assembler.render_markdown(stored) == result["markdown"]


def test_introduction_uses_question_context_sections_and_counts():
    intro = build()["report"]["introduction"]
    joined = " ".join(intro)
    assert "How do vision transformers compare with CNNs?" in joined and "Deep learning for image classification" in joined
    assert "3 sub-questions" in joined and "(1) How do vision transformers" in joined and "7 claims" in joined and "5 documents" in joined
    assert "reviewed by a person" in joined


# ------------------------------------------------------------------------------------------------------------ insufficient evidence
def test_stage4_error_gives_insufficient_evidence_and_no_llm_call():
    llm = FakeLLM()
    inputs = empty_inputs(fact_error="RuntimeError: database stayed unreachable")
    result = build(inputs, llm=llm)
    assert result["status"] == "insufficient_evidence" and result["report"]["status"] == "insufficient_evidence"
    assert llm.calls == [] and result["stats"]["calls"] == 0 and result["stats"]["tokens"] == 0
    assert any("Fact checking (Stage 4) failed" in x and "database stayed unreachable" in x for x in result["report"]["limitations"])
    assert [s["sentences"] for s in result["report"]["sections"]] == [[], [], []]
    assert all(s["gaps"] for s in result["report"]["sections"])
    assert "## Conclusion" in result["markdown"] and "No executive summary could be written" in result["markdown"]


def test_no_claims_at_all_is_insufficient_not_failed():
    llm = FakeLLM()
    result = build(empty_inputs(), llm=llm)
    assert result["status"] == "insufficient_evidence" and llm.calls == []
    assert any("produced no checked claims" in x for x in result["report"]["limitations"])


def test_only_disputed_and_filtered_claims_is_insufficient_but_shows_the_disagreement():
    inputs = make_inputs()
    inputs["sub_questions"] = [inputs["sub_questions"][1]]
    inputs["sub_questions"][0]["claims"] = inputs["sub_questions"][0]["claims"][:1]          # only the contradicted claim
    llm = FakeLLM()
    result = build(inputs, llm=llm)
    assert result["status"] == "insufficient_evidence" and llm.calls == []
    assert len(result["report"]["sections"][0]["disagreements"]) == 1 and "#### Sources disagree" in result["markdown"]


# ------------------------------------------------------------------------------------------------------------ failures of the model
def test_failing_llm_gives_fallback_sentences_and_warnings():
    llm = FakeLLM(fail=RuntimeError("boom"))
    result = build(llm=llm)
    report = result["report"]
    assert result["status"] == "completed_with_warnings"
    sentences = [s for sec in report["sections"] for s in sec["sentences"]]
    assert len(sentences) == 4 and all(s["origin"] == "fallback" for s in sentences)
    assert sentences[0]["text"].startswith("Two sources report that") and sentences[2]["text"].startswith("One study reports that")
    assert all(s["refs"] for s in sentences)
    assert result["stats"]["sentences"]["fallback"] == 4 and result["stats"]["sentences"]["llm"] == 0
    assert any("fixed template wording" in x for x in report["limitations"])
    assert report["overview"]["summary"] and all(s["origin"] == "fallback" for s in report["overview"]["summary"])      # extractive after the failed call
    assert result["stats"]["summary_fallback"] is True


def test_a_sentence_that_fails_the_check_twice_uses_the_fallback_and_is_reported():
    def strict(text, ids, job):
        return ["the number is wrong"] if "Hybrid models" in text and text.startswith("One study reports that") else []
    events = []
    result = build(llm=FakeLLM(), check=strict, progress=lambda step, message="", **data: events.append((step, data)))
    s1 = result["report"]["sections"][0]["sentences"]
    hybrid = next(s for s in s1 if "Hybrid" in s["text"])
    assert hybrid["origin"] == "fallback" and hybrid["text"].startswith("One study reports that Hybrid models")
    assert [s["origin"] for s in s1 if s is not hybrid] == ["llm", "llm"]
    assert result["status"] == "completed_with_warnings" and result["stats"]["retried"] == 1 and result["stats"]["sentences"]["fallback"] == 1
    assert ("note", {"code": "stage5_fallback", "level": "warn", "count": 1}) in events
    assert hybrid["attempts"] == 2 and hybrid["reasons"] == ["the number is wrong", "the number is wrong"]      # the audit trail is stored
    assert all(s["attempts"] == 1 and "reasons" not in s for s in s1 if s is not hybrid)


# ------------------------------------------------------------------------------------------------------------ the summary check
def test_summary_with_a_new_number_is_rejected_and_the_extractive_template_is_used():
    llm = FakeLLM(bad_summary="One study reports that hybrid models converge 47% faster in early training.")
    result = build(llm=llm)
    report = result["report"]
    summary = report["overview"]["summary"]
    assert summary and all(s["origin"] == "fallback" for s in summary)
    assert all("47" not in s["text"] for s in summary)
    body = [s["text"] for sec in report["sections"] for s in sec["sentences"]]
    assert all(s["text"] in body for s in summary)                              # word-for-word copies, nothing new
    assert llm.purposes("stage5_summary").count("stage5_summary") == 3          # summary: first try + retry; conclusion: one call
    assert result["status"] == "completed_with_warnings" and result["stats"]["summary_fallback"] is True
    assert result["stats"]["conclusion_fallback"] is False


def test_the_single_source_share_sentence_is_added_only_when_most_findings_are_single():
    inputs = make_inputs()
    sq = inputs["sub_questions"][0]
    sq["claims"] = [row("sq1", f"Model {i} converges faster in early training.", "unverified",
                        [ev(f"s{i}", f"Paper number {i}", f"Model {i} converges quickly.")]) for i in range(4)]
    inputs["sub_questions"] = [sq]
    result = build(inputs)
    summary = result["report"]["overview"]["summary"]
    assert summary[-1]["origin"] == "template" and summary[-1]["text"] == assembler.SINGLE_SHARE_SENTENCE and summary[-1]["claimIds"] == [] and summary[-1]["refs"] == []
    assert result["status"] == "completed" and result["warnings"] == []
    mixed = build()["report"]["overview"]["summary"]
    assert all(s["origin"] != "template" for s in mixed)


# ------------------------------------------------------------------------------------------------------------ deterministic mode
def test_deterministic_mode_makes_zero_llm_and_model_calls():
    llm = FakeLLM()
    nli_calls = []
    result = assembler.build_report(make_inputs(), llm=llm, nli=lambda pairs: nli_calls.append(pairs), judge=lambda *a: nli_calls.append(a), deterministic=True)
    assert llm.calls == [] and nli_calls == [] and result["stats"]["calls"] == 0 and result["stats"]["tokens"] == 0
    assert result["model"] == "deterministic"
    report = result["report"]
    sentences = [s for sec in report["sections"] for s in sec["sentences"]]
    assert len(sentences) == 4 and all(s["origin"] == "fallback" for s in sentences)
    assert report["overview"]["summary"] and all(s["origin"] == "template" for s in report["overview"]["summary"])
    assert result["status"] == "completed_with_warnings" and any("Deterministic mode" in w for w in result["warnings"])
    assert report["references"] and "[1" in result["markdown"]


# ------------------------------------------------------------------------------------------------------------ the real check chain with fake models
def test_default_check_uses_the_injected_nli_and_judge():
    pairs, judged = [], []

    def nli(batch):
        pairs.extend(batch)
        return [{"entailment": 0.95, "contradiction": 0.01, "neutral": 0.04} for _ in batch]

    result = assembler.build_report(make_inputs(), llm=FakeLLM(), nli=nli, judge=lambda *a: judged.append(a), cache=False, workers=1)
    assert pairs and judged == []
    assert result["stats"]["nli"]["pairs"] == len(pairs) > 0
    assert result["stats"]["sentences"]["llm"] == 4 and result["status"] == "completed"


def test_nli_contradiction_rejects_the_sentence_and_the_fallback_takes_over():
    def nli(batch):
        return [{"entailment": 0.0, "contradiction": 0.9, "neutral": 0.1} for _ in batch]

    result = assembler.build_report(make_inputs(), llm=FakeLLM(), nli=nli, judge=lambda *a: {"supports": True, "confidence": 1.0}, cache=False, workers=1)
    assert result["stats"]["sentences"]["llm"] == 0 and result["stats"]["sentences"]["fallback"] == 4 and result["status"] == "completed_with_warnings"
    assert result["stats"]["nli"]["contradiction_rejects"] > 0


# ------------------------------------------------------------------------------------------------------------ never raises, final checks
def test_build_report_never_raises():
    for bad in (None, {}, {"sub_questions": "x"}, {"sub_questions": [{"id": "a", "claims": [{"claim": "x", "evidence": 5}]}]}):
        result = assembler.build_report(bad, llm=FakeLLM(), check=ok_check, cache=False)
        assert result["status"] in ("insufficient_evidence", "completed", "completed_with_warnings", "failed")
        assert set(result) == {"status", "report", "markdown", "stats", "warnings", "model", "template_version"}
    boom = assembler.build_report(make_inputs(), llm=FakeLLM(), check=ok_check, cache=False, progress=None, workers="not a number")
    assert boom["status"] in ("completed", "failed") and boom["markdown"]


def test_an_internal_error_gives_status_failed_with_the_error_in_the_warnings(monkeypatch):
    def explode(*a, **k):
        raise ValueError("internal bug")
    monkeypatch.setattr(assembler.tiers, "build_claims", explode)
    result = assembler.build_report(make_inputs(), llm=FakeLLM(), check=ok_check, cache=False)
    assert result["status"] == "failed" and result["report"]["status"] == "failed"
    assert any("internal bug" in w for w in result["warnings"]) and result["report"]["sections"] == [] and "# How do vision transformers" in result["markdown"]


def test_progress_errors_are_swallowed_and_steps_are_reported_in_order():
    steps = []

    def prog(step, message="", **data):
        steps.append((step, data.get("state", "running")))
        raise RuntimeError("the sink is broken")
    result = build(progress=prog)
    assert result["status"] == "completed"
    names = [s for s, _ in steps]
    assert names[0] == "sections" and ("sections", "completed") in steps
    assert names.index("write") < names.index("validate") < names.index("summary") < names.index("references")
    assert steps[-1] == ("references", "completed")


def test_final_checks_flag_unknown_claim_ids_missing_refs_and_empty_sections():
    result = build()
    report = json.loads(json.dumps(result["report"]))
    claims_by_id = {c.claim_id: c for c in assembler.tiers.build_claims(make_inputs()["sub_questions"])}
    assert assembler.final_checks(report, claims_by_id, [], [], []) == []
    report["sections"][0]["sentences"][0]["claimIds"] = ["c_missing"]
    report["sections"][0]["sentences"][1]["refs"] = [99]
    report["sections"][2]["gaps"] = []
    report["sections"][0]["sentences"][2]["text"] = "One study reports that x [3]."
    warnings = assembler.final_checks(report, claims_by_id, [], [], [])
    assert any("unknown claim id" in w for w in warnings) and any("do not exist" in w for w in warnings)
    assert any("no text and no gap message" in w for w in warnings) and any("citation marker" in w for w in warnings)


# ------------------------------------------------------------------------------------------------------------ the node
def state_for(fact=True):
    plan = SimpleNamespace(query_id="q1", domain_context="", sub_questions=[])
    return SimpleNamespace(raw_query="How do vision transformers compare with CNNs?", query_id="q1", task_plan=plan,
                           fact_claims=[{"claim": "x"}] if fact else [], fact_summary={"sq1": {"total": 1}} if fact else {})


class Sink:
    def __init__(self, qid="q1"):
        self.events = []
        progress.register(qid, self.events.append)
        self.qid = qid

    def close(self):
        progress.unregister(self.qid)


@pytest.fixture
def sink():
    s = Sink()
    yield s
    s.close()


@pytest.fixture
def fake_pipeline(monkeypatch):
    """The node with fake inputs (no database), a fake model and a recording persistence function."""
    saved = []
    monkeypatch.setattr(report_node.loader, "from_state", lambda state, **kw: make_inputs())
    real = assembler.build_report
    monkeypatch.setattr(report_node.assembler, "build_report", lambda inputs, **kw: real(inputs, llm=FakeLLM(), check=ok_check, cache=False, workers=1, **kw))
    fake_db = types.ModuleType("db_service")
    fake_db.write_written_report = lambda *args: saved.append(args)
    monkeypatch.setitem(sys.modules, "apps.api.services.db_service", fake_db)
    monkeypatch.setattr("apps.api.services.db_service", fake_db, raising=False)
    return saved


def test_report_node_does_nothing_when_stage5_is_off(sink, fake_pipeline):
    assert report_node.report_node(state_for()) == {}
    assert sink.events == [] and fake_pipeline == []


def test_report_node_skips_when_stage4_did_not_run_and_leaves_a_note(monkeypatch, sink, fake_pipeline):
    monkeypatch.setenv("STAGE5", "true")
    assert report_node.report_node(state_for(fact=False)) == {}
    notes = [e for e in sink.events if e["lane"] == "notes"]
    assert len(notes) == 1 and notes[0]["step"] == "stage5_skipped" and notes[0]["data"]["stage"] == "report" and notes[0]["data"]["level"] == "info"
    assert fake_pipeline == [] and not [e for e in sink.events if e["lane"] == "report"]


def test_report_node_builds_persists_and_returns_the_state_fields(monkeypatch, sink, fake_pipeline):
    monkeypatch.setenv("STAGE5", "true")
    out = report_node.report_node(state_for())
    assert set(out) == {"written_report", "written_report_status"} and out["written_report_status"] == "completed"
    assert out["written_report"]["status"] == "completed" and len(out["written_report"]["sections"]) == 3
    (qid, status, report, markdown, stats, model, version), = fake_pipeline
    assert qid == "q1" and status == "completed" and report == out["written_report"] and markdown.startswith("# ") and stats["calls"] > 0
    assert model == "openai/gpt-oss-120b" and version == "s5-v1"
    report_events = [e for e in sink.events if e["lane"] == "report"]
    steps = [(e["step"], e["state"]) for e in report_events]
    assert steps[0] == ("branch", "running") and ("sections", "completed") in steps and ("references", "completed") in steps and steps[-1] == ("store", "completed")
    assert {"sections", "write", "validate", "summary", "references"} <= {s for s, _ in steps}
    for e in report_events:                                    # counts only: no text in the event data
        assert all(isinstance(v, (int, float, bool)) for v in e["data"].values())


def test_report_node_tolerates_a_missing_or_failing_persistence_function(monkeypatch, sink, fake_pipeline):
    monkeypatch.setenv("STAGE5", "true")
    fake_db = sys.modules["apps.api.services.db_service"]
    del fake_db.write_written_report
    out = report_node.report_node(state_for())
    assert out["written_report_status"] == "completed"
    fake_db.write_written_report = lambda *a: (_ for _ in ()).throw(RuntimeError("db down"))
    out = report_node.report_node(state_for())
    assert out["written_report_status"] == "completed" and out["written_report"]["sections"]
    assert any(e["step"] == "store" and e["data"]["stored"] is False for e in sink.events)


def test_report_node_never_raises(monkeypatch, sink, fake_pipeline):
    monkeypatch.setenv("STAGE5", "true")
    monkeypatch.setattr(report_node.loader, "from_state", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no database")))
    out = report_node.report_node(state_for())
    assert out["written_report_status"] == "failed" and any("no database" in w for w in out["written_report"]["warnings"])
    monkeypatch.setattr(report_node.loader, "from_state", lambda *a, **k: make_inputs())
    monkeypatch.setattr(report_node.assembler, "build_report", lambda *a, **k: (_ for _ in ()).throw(KeyError("oops")))
    out = report_node.report_node(state_for())
    assert out["written_report_status"] == "failed"
    out = report_node.report_node(object())                     # a state with nothing in it
    assert out == {} or out["written_report_status"] in ("failed", "insufficient_evidence")


# ------------------------------------------------------------------------------------------------------------ the script
def load_script():
    spec = importlib.util.spec_from_file_location("stage5_on_stored_run", ROOT / "scripts" / "stage5_on_stored_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_dry_run_writes_markdown_and_json_with_fakes(tmp_path):
    script = load_script()
    printed = []
    asked = []
    real = assembler.build_report

    def build(inputs, **kw):
        asked.append(kw)
        return real(inputs, llm=FakeLLM(fail=AssertionError("the dry run must not call the model")), **kw)

    code = script.main(["--run", "q1", "--out", str(tmp_path / "out" / "q1.md"), "--dry"], load=lambda q: make_inputs(), build=build, write=printed.append)
    assert code == 0 and asked == [{"deterministic": True}]
    md, js = tmp_path / "out" / "q1.md", tmp_path / "out" / "q1.json"
    assert md.read_text(encoding="utf-8").startswith("# How do vision transformers") and js.exists()
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["status"] == "completed_with_warnings" and payload["report"]["sections"] and "markdown" not in payload
    out = "\n".join(printed)
    assert "status completed_with_warnings" in out and "section 3" in out and "tokens 0" in out and "claims 7: supported 1, partly 1, single 2, disputed 1" in out


def test_script_reports_an_unknown_run_and_default_output_path(tmp_path, monkeypatch):
    script = load_script()
    printed = []
    assert script.main(["--run", "nope"], load=lambda q: {"status_hints": {"found": False}}, build=None, write=printed.append) == 2
    assert "not found" in printed[0]
    assert script.output_base(None, "abc") == Path("reports") / "stage5" / "abc"
    assert script.output_base(str(tmp_path / "x.json"), "abc") == tmp_path / "x"
    assert script.output_base(str(tmp_path) + "/", "abc") == tmp_path / "abc"
    monkeypatch.chdir(tmp_path)
    assert script.main(["--run", "q1", "--dry"], load=lambda q: make_inputs(), write=lambda *a: None) == 0
    assert (tmp_path / "reports" / "stage5" / "q1.md").exists() and (tmp_path / "reports" / "stage5" / "q1.json").exists()


# ------------------------------------------------------------------------------------------------------- fallback sentences are one per claim
def test_a_fallback_sentence_with_several_claims_is_split_into_one_sentence_per_claim():
    from apps.api.agents.stage5_report import assembler
    from apps.api.agents.stage5_report.schema import Claim, Evidence, Sentence, ORIGIN_FALLBACK, ORIGIN_LLM, TIER_SINGLE
    def claim(n):
        return Claim(claim_id=f"c_{n}", sub_question_id="q1", text=f"Claim number {n} holds", label="unverified", tier=TIER_SINGLE,
                     evidence=[Evidence(source_id=f"s{n}", title=f"Doc {n}", quote="q", ref_key=f"doc {n}")])
    by_id = {c.claim_id: c for c in (claim(1), claim(2), claim(3))}
    joined = Sentence(text="joined", claim_ids=["c_1", "c_2", "c_3"], job_id="j1", tier=TIER_SINGLE, origin=ORIGIN_FALLBACK, attempts=2, reasons=["x"])
    written = Sentence(text="llm text", claim_ids=["c_1", "c_2"], job_id="j2", tier=TIER_SINGLE, origin=ORIGIN_LLM)
    out = assembler._split_fallbacks([joined, written], by_id, "s1")
    assert [s.claim_ids for s in out] == [["c_1"], ["c_2"], ["c_3"], ["c_1", "c_2"]]      # the LLM sentence is untouched
    assert all(s.origin == ORIGIN_FALLBACK and s.reasons == ["x"] for s in out[:3]) and out[0].text.startswith("One study reports that")
    assert [s.job_id for s in out[:3]] == ["j1.1", "j1.2", "j1.3"]
