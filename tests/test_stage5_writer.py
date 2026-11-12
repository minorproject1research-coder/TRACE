"""Stage 5 writer: settings, prompts, write_section (splitting, retry, fallback, 413, cache, threads) and summary / conclusion.

All offline: the LLM, the checks and the fallback are fakes; nothing reaches Groq, a model or the network.
"""
import json
import sys
import threading
import time
import types

import pytest

from apps.api.agents.stage5_report import prompts, settings, summary, writer
from apps.api.agents.stage5_report.schema import (ORIGIN_FALLBACK, ORIGIN_LLM, ORIGIN_TEMPLATE, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED, Claim,
                                                  Evidence, Job, Sentence)

_ENV = ("STAGE5", "STAGE5_MODEL", "STAGE5_REASONING_EFFORT", "STAGE5_MAX_OUTPUT_TOKENS", "STAGE5_MAX_PROMPT_TOKENS", "STAGE5_TEMPERATURE", "STAGE5_RETRIES",
        "STAGE5_WORKERS", "STAGE5_CACHE", "STAGE5_CACHE_DIR", "STAGE5_RATE_WAIT_MAX", "STAGE5_RATE_RETRIES", "STAGE5_BREAKER_SECONDS")


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)           # the real .env may set some of them
    monkeypatch.setenv("STAGE5_CACHE_DIR", str(tmp_path / "s5cache"))
    writer.default_rate.reset()
    yield
    writer.default_rate.reset()


# ------------------------------------------------------------------------------------------------------------ builders and fakes
def claim(cid, text=None, tier=TIER_SINGLE, quote=None, near=None):
    ev = [Evidence(source_id="s_" + cid, title="Title " + cid, quote=quote or f"verbatim quote of {cid}", ref_key="doc_" + cid)]
    if near:
        ev.append(Evidence(source_id="s2_" + cid, title="Other", quote="other quote", relation="near_match", near_claim=near, ref_key="other_" + cid))
    return Claim(claim_id=cid, sub_question_id="sq1", text=text or f"Model A gains 12 points on task {cid}.", label="unverified", tier=tier, evidence=ev)


def job(jid, cids, tier=TIER_SINGLE, **kw):
    return Job(job_id=jid, section_id="sec1", tier=tier, claims=[claim(c, tier=tier, **kw) for c in cids])


def jobs(n, **kw):
    return [job(f"j{i}", [f"c{i}"], **kw) for i in range(n)]


def sentence_for(j, suffix=""):
    return {"job_id": j.job_id, "text": f"One study reports that {j.claims[0].text}{suffix}", "claim_ids": [c.claim_id for c in j.claims]}


def requested_ids(response_format):
    return response_format["json_schema"]["schema"]["properties"]["sentences"]["items"]["properties"]["job_id"]["enum"]


class FakeLLM:
    """Records every call; `reply(call_no, messages, response_format, purpose)` returns a dict, a (dict, usage) tuple or raises."""

    def __init__(self, reply, delay=0.0):
        self.reply, self.delay = reply, delay
        self.calls = []
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def __call__(self, messages, response_format, purpose):
        with self.lock:
            self.calls.append({"messages": messages, "format": response_format, "purpose": purpose})
            n = len(self.calls)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            return self.reply(n, messages, response_format, purpose)
        finally:
            with self.lock:
                self.active -= 1


def answer_all(job_list):
    """A reply function that writes a good sentence for every job that is requested in the call."""
    by_id = {j.job_id: j for j in job_list}

    def reply(n, messages, fmt, purpose):
        return {"sentences": [sentence_for(by_id[i]) for i in requested_ids(fmt)]}
    return reply


def ok_check(text, ids, j):
    return []


def fb(j):
    return f"FALLBACK {j.job_id}"


def run(job_list, llm, **kw):
    kw.setdefault("check", ok_check)
    kw.setdefault("fallback", fb)
    kw.setdefault("cache", False)
    kw.setdefault("tier_rules", {})
    return writer.write_section("How does A compare with B?", job_list, llm=llm, **kw)


# ------------------------------------------------------------------------------------------------------------ settings
def test_settings_defaults():
    assert settings.stage5_enabled() is False
    assert settings.model() == "openai/gpt-oss-120b"
    assert settings.retries() == 1
    assert settings.max_prompt_tokens() == 4500
    assert settings.max_output_tokens() == 2500
    assert settings.reasoning_effort() == "low"
    assert settings.workers() == 3
    assert settings.cache_enabled() is True
    assert settings.rate_wait_max() == 300
    assert settings.template_version() == "s5-v1"


def test_settings_env_overrides_and_bad_values(monkeypatch):
    monkeypatch.setenv("STAGE5", "yes")
    monkeypatch.setenv("STAGE5_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("STAGE5_RETRIES", "0")
    monkeypatch.setenv("STAGE5_MAX_PROMPT_TOKENS", "1234")
    monkeypatch.setenv("STAGE5_WORKERS", "0")                  # at least 1
    monkeypatch.setenv("STAGE5_CACHE", "off")
    monkeypatch.setenv("STAGE5_REASONING_EFFORT", "HIGH")
    monkeypatch.setenv("STAGE5_RATE_WAIT_MAX", "12.5")
    assert settings.stage5_enabled() is True
    assert settings.model() == "openai/gpt-oss-20b"
    assert settings.retries() == 0
    assert settings.max_prompt_tokens() == 1234
    assert settings.workers() == 1
    assert settings.cache_enabled() is False
    assert settings.reasoning_effort() == "high"
    assert settings.rate_wait_max() == 12.5
    monkeypatch.setenv("STAGE5_MAX_OUTPUT_TOKENS", "lots")
    monkeypatch.setenv("STAGE5_REASONING_EFFORT", "extreme")
    monkeypatch.setenv("STAGE5_MODEL", "  ")
    assert settings.max_output_tokens() == 2500
    assert settings.reasoning_effort() == "low"
    assert settings.model() == "openai/gpt-oss-120b"


# ------------------------------------------------------------------------------------------------------------ prompts
def test_write_prompt_has_jobs_claims_quotes_and_no_citations():
    js = [job("j1", ["c1", "c2"]), job("j2", ["c3"], tier=TIER_PARTLY, near="The other source says something close.")]
    msgs = prompts.write_messages("Section title", js, {TIER_SINGLE: {"instruction": "SINGLE RULE FROM HEDGING"}, TIER_PARTLY: "PARTLY RULE"})
    text = msgs[0]["content"] + msgs[1]["content"]
    for needle in ("JOB j1", "JOB j2", "claim c1", "claim c2", "claim c3", "verbatim quote of c1", "SINGLE RULE FROM HEDGING", "PARTLY RULE",
                   "related wording from another source", "The other source says something close.", "ONE sentence", "Section title"):
        assert needle in text
    assert "http" not in msgs[1]["content"] and "[1]" not in msgs[1]["content"]
    assert prompts.write_messages("Section title", js, {}) == prompts.write_messages("Section title", js, {})     # deterministic (cache key)


def test_tier_instruction_falls_back_to_default():
    assert "Two sources report" in prompts.tier_instruction(TIER_SUPPORTED, None)
    assert prompts.tier_instruction(TIER_SINGLE, {TIER_SINGLE: "custom"}) == "custom"
    assert prompts.tier_instruction(TIER_SINGLE, {TIER_SINGLE: {"nothing": 1}}) == prompts.DEFAULT_TIER_TEXT[TIER_SINGLE]


def test_section_schema_is_strict_with_enums():
    fmt = prompts.section_schema([job("j1", ["c1", "c2"]), job("j2", ["c2", "c3"])])
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    item = fmt["json_schema"]["schema"]["properties"]["sentences"]["items"]
    assert item["additionalProperties"] is False and set(item["required"]) == {"job_id", "text", "claim_ids"}
    assert item["properties"]["job_id"]["enum"] == ["j1", "j2"]
    assert item["properties"]["claim_ids"]["items"]["enum"] == ["c1", "c2", "c3"]
    json.dumps(fmt)


def test_retry_prompt_carries_the_python_reasons():
    j = job("j1", ["c1"])
    msgs = prompts.retry_messages("S", [j], {"j1": {"text": "bad sentence 17%", "reasons": ["the number 17% is not in the claims"]}}, {})
    body = msgs[1]["content"]
    assert "bad sentence 17%" in body and "the number 17% is not in the claims" in body and "JOB j1" in body


def test_summary_prompt_numbers_the_sentences():
    msgs = prompts.summary_messages("summary", [{"n": 1, "text": "First.", "tier": "supported"}, {"n": 2, "text": "Second.", "tier": "single"}], 3, 5)
    assert "1. [supported] First." in msgs[1]["content"] and "2. [single] Second." in msgs[1]["content"]
    assert "3 to 5 sentences" in msgs[0]["content"]
    assert "conclusion" in prompts.summary_messages("conclusion", [{"n": 1, "text": "A.", "tier": "single"}], 3, 4)[0]["content"]
    assert prompts.summary_schema([1, 2])["json_schema"]["schema"]["properties"]["sentences"]["items"]["properties"]["from_sentences"]["items"]["enum"] == [1, 2]


# ------------------------------------------------------------------------------------------------------------ splitting under the cap
def test_jobs_are_split_under_the_prompt_cap(monkeypatch):
    long = "x" * 270
    js = [job(f"j{i}", [f"c{i}"], quote=long) for i in range(12)]
    monkeypatch.setenv("STAGE5_MAX_PROMPT_TOKENS", "700")
    groups = writer.split_jobs("S", js, {})
    assert len(groups) > 1 and [j.job_id for g in groups for j in g] == [j.job_id for j in js]       # order kept, nothing lost
    for g in groups:
        assert prompts.estimate_messages_tokens(prompts.write_messages("S", g, {})) <= 700 or len(g) == 1
    llm = FakeLLM(answer_all(js))
    sentences, stats = run(js, llm)
    assert stats["calls"] == len(groups) == len(llm.calls)
    assert [s.job_id for s in sentences] == [j.job_id for j in js]
    assert all(s.origin == ORIGIN_LLM for s in sentences)


def test_one_job_bigger_than_the_cap_goes_alone(monkeypatch):
    monkeypatch.setenv("STAGE5_MAX_PROMPT_TOKENS", "200")
    groups = writer.split_jobs("S", jobs(3), {})
    assert [len(g) for g in groups] == [1, 1, 1]


def test_default_cap_keeps_a_small_section_in_one_call():
    js = jobs(6)
    llm = FakeLLM(answer_all(js))
    _, stats = run(js, llm)
    assert stats["calls"] == 1 and stats["jobs"] == 6


# ------------------------------------------------------------------------------------------------------------ the happy path
def test_happy_path_sentences_stats_and_call_arguments():
    js = jobs(3)
    llm = FakeLLM(lambda n, m, f, p: (answer_all(js)(n, m, f, p), {"prompt_tokens": 100, "completion_tokens": 40}))
    sentences, stats = run(js, llm)
    assert [s.origin for s in sentences] == [ORIGIN_LLM] * 3 and [s.attempts for s in sentences] == [1] * 3
    assert sentences[0].claim_ids == ["c0"] and sentences[0].tier == TIER_SINGLE and sentences[0].job_id == "j0"
    assert llm.calls[0]["purpose"] == "stage5_write" and llm.calls[0]["format"]["json_schema"]["strict"] is True
    assert stats["calls"] == 1 and stats["prompt_tokens"] == 100 and stats["completion_tokens"] == 40 and stats["total_tokens"] == 140
    assert stats["fallback"] == 0 and stats["retried"] == 0 and stats["llm_sentences"] == 3


def test_text_is_whitespace_normalised_and_ids_deduped():
    j = job("j0", ["c0"])
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [{"job_id": "j0", "text": "  One study\nreports   it. ", "claim_ids": ["c0", "c0"]}]})
    (s,), _ = run([j], llm)
    assert s.text == "One study reports it." and s.claim_ids == ["c0"]


def test_empty_jobs():
    assert run([], FakeLLM(lambda *a: {}))[0] == []


# ------------------------------------------------------------------------------------------------------------ retry then fallback
def test_one_retry_with_the_reasons_then_accepted():
    js = jobs(2)
    seen = []

    def reply(n, m, f, p):
        if n == 1:
            return {"sentences": [sentence_for(js[0], " BAD"), sentence_for(js[1])]}
        return {"sentences": [sentence_for(requested, "") for requested in js if requested.job_id in requested_ids(f)]}

    def check(text, ids, j):
        seen.append(j.job_id)
        return ["the number 99 is not in the claims"] if "BAD" in text else []

    llm = FakeLLM(reply)
    sentences, stats = run(js, llm, check=check)
    assert len(llm.calls) == 2 and requested_ids(llm.calls[1]["format"]) == ["j0"]           # only the failed job is asked again
    assert "the number 99 is not in the claims" in llm.calls[1]["messages"][1]["content"]
    assert "BAD" in llm.calls[1]["messages"][1]["content"]                                     # the previous sentence is shown too
    assert [s.attempts for s in sentences] == [2, 1] and all(s.origin == ORIGIN_LLM for s in sentences)
    assert sentences[0].reasons == ["the number 99 is not in the claims"]
    assert stats["retried"] == 1 and stats["fallback"] == 0 and stats["calls"] == 2


def test_failing_twice_gives_the_fallback_sentence():
    js = jobs(2)
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(j, " BAD") for j in js if j.job_id in requested_ids(f)]})
    sentences, stats = run(js, llm, check=lambda t, i, j: ["strong verb"] if "BAD" in t else [])
    assert len(llm.calls) == 2                                          # exactly one retry
    assert [s.text for s in sentences] == ["FALLBACK j0", "FALLBACK j1"]
    assert all(s.origin == ORIGIN_FALLBACK and s.attempts == 2 and s.reasons == ["strong verb", "strong verb"] for s in sentences)
    assert all(s.claim_ids == [j.claims[0].claim_id] for s, j in zip(sentences, js))
    assert stats["fallback"] == 2 and stats["retried"] == 2


def test_retries_zero_means_no_second_call(monkeypatch):
    monkeypatch.setenv("STAGE5_RETRIES", "0")
    j = job("j0", ["c0"])
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(j)]})
    sentences, stats = run([j], llm, check=lambda t, i, jj: ["no"])
    assert len(llm.calls) == 1 and sentences[0].origin == ORIGIN_FALLBACK and stats["retried"] == 0


def test_fallback_may_return_an_object_with_text_and_ids():
    j = job("j0", ["c0", "c1"])
    llm = FakeLLM(lambda n, m, f, p: {"sentences": []})
    s1, _ = run([j], llm, fallback=lambda jj: types.SimpleNamespace(text="Object text.", claim_ids=["c1"]))
    assert s1[0].text == "Object text." and s1[0].claim_ids == ["c1"]
    s2, _ = run([j], llm, fallback=lambda jj: {"text": "Dict text."})
    assert s2[0].text == "Dict text." and s2[0].claim_ids == ["c0", "c1"]


def test_a_broken_fallback_uses_the_last_resort_wording():
    def boom(j):
        raise RuntimeError("hedging missing")
    j = job("j0", ["c0"])
    s, stats = run([j], FakeLLM(lambda n, m, f, p: {"sentences": []}), fallback=boom)
    assert s[0].origin == ORIGIN_FALLBACK and s[0].text.startswith("One study reports that ") and "Model A gains 12 points" in s[0].text
    assert stats["fallback"] == 1


# ------------------------------------------------------------------------------------------------------------ bad replies
def test_job_missing_from_the_reply_is_a_failure_and_retried():
    js = jobs(3)
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(j) for j in js if j.job_id in requested_ids(f) and (n > 1 or j.job_id != "j1")]})
    sentences, stats = run(js, llm)
    assert len(llm.calls) == 2 and requested_ids(llm.calls[1]["format"]) == ["j1"]
    assert "no sentence was returned" in llm.calls[1]["messages"][1]["content"]
    assert [s.attempts for s in sentences] == [1, 2, 1] and stats["retried"] == 1


def test_job_missing_twice_falls_back():
    js = jobs(2)
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(js[0])]})
    sentences, _ = run(js, llm)
    assert sentences[0].origin == ORIGIN_LLM and sentences[1].origin == ORIGIN_FALLBACK and sentences[1].text == "FALLBACK j1"


def test_foreign_job_ids_and_duplicates_in_the_reply_are_ignored():
    js = jobs(1)
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [{"job_id": "zzz", "text": "x", "claim_ids": ["c0"]}, sentence_for(js[0]),
                                                      {"job_id": "j0", "text": "Second answer.", "claim_ids": ["c0"]}]})
    (s,), _ = run(js, llm)
    assert s.text.startswith("One study reports") and len(llm.calls) == 1


def test_a_foreign_claim_id_next_to_an_own_one_is_dropped_not_cited():
    j = job("j0", ["c0", "c1"])
    seen = []

    def check(text, ids, jj):
        seen.append(list(ids))
        return []

    llm = FakeLLM(lambda n, m, f, p: {"sentences": [{"job_id": "j0", "text": "One study reports it.", "claim_ids": ["c0", "c9"]}]})
    s, _ = run([j], llm, check=check)
    assert s[0].origin == ORIGIN_LLM and s[0].claim_ids == ["c0"] and seen == [["c0"]] and len(llm.calls) == 1      # c9 never reaches the check or a citation


def test_foreign_claim_ids_never_reach_the_check():
    called = []
    j = job("j0", ["c0"])
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [{"job_id": "j0", "text": "One study reports it.", "claim_ids": ["other"]}]})
    s, _ = run([j], llm, check=lambda t, i, jj: called.append(1) or [])
    assert called == [] and s[0].origin == ORIGIN_FALLBACK
    assert "do not belong to this job" in s[0].reasons[0]


def test_empty_text_and_missing_ids_are_rejected():
    j = job("j0", ["c0"])
    for entry in ({"job_id": "j0", "text": "  ", "claim_ids": ["c0"]}, {"job_id": "j0", "text": "ok.", "claim_ids": []},
                  {"job_id": "j0", "text": "ok.", "claim_ids": "c0"}, {"job_id": "j0", "text": 5, "claim_ids": ["c0"]}):
        s, _ = run([j], FakeLLM(lambda n, m, f, p, e=entry: {"sentences": [e]}))
        assert s[0].origin == ORIGIN_FALLBACK


def test_malformed_json_is_a_failed_attempt_then_retried():
    j = job("j0", ["c0"])

    def reply(n, m, f, p):
        if n == 1:
            raise json.JSONDecodeError("Expecting property name", "{", 1)
        return {"sentences": [sentence_for(j)]}
    llm = FakeLLM(reply)
    (s,), stats = run([j], llm)
    assert s.origin == ORIGIN_LLM and s.attempts == 2 and stats["malformed"] == 1 and stats["retried"] == 1 and len(llm.calls) == 2


@pytest.mark.parametrize("bad", [["not", "a", "dict"], {"nothing": 1}, {"sentences": "text"}])
def test_reply_with_the_wrong_shape_counts_as_malformed(bad):
    j = job("j0", ["c0"])
    llm = FakeLLM(lambda n, m, f, p: bad)
    (s,), stats = run([j], llm)
    assert s.origin == ORIGIN_FALLBACK and stats["malformed"] == 2 and len(llm.calls) == 2


def test_check_that_raises_fails_closed():
    j = job("j0", ["c0"])

    def check(t, i, jj):
        raise RuntimeError("nli exploded")
    (s,), _ = run([j], FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(j)]}), check=check)
    assert s.origin == ORIGIN_FALLBACK and "could not run" in s.reasons[0]


# ------------------------------------------------------------------------------------------------------------ LLM errors, rate limits, 413
def test_llm_exception_gives_the_fallback_for_that_call_only(monkeypatch):
    long = "x" * 270
    js = [job(f"j{i}", [f"c{i}"], quote=long) for i in range(6)]
    monkeypatch.setenv("STAGE5_MAX_PROMPT_TOKENS", "700")
    groups = writer.split_jobs("S", js, {})
    assert len(groups) >= 2
    first_ids = {j.job_id for j in groups[0]}
    good = answer_all(js)

    def reply(n, m, f, p):
        if set(requested_ids(f)) == first_ids:
            raise ConnectionError("network down")
        return good(n, m, f, p)
    llm = FakeLLM(reply)
    sentences, stats = run(js, llm)
    for s in sentences:
        assert s.origin == (ORIGIN_FALLBACK if s.job_id in first_ids else ORIGIN_LLM)
    assert stats["llm_errors"] == 1 and stats["calls"] == len(groups)           # no retry for a hard error


def test_rate_limit_waits_then_succeeds():
    j = job("j0", ["c0"])
    sleeps = []

    def reply(n, m, f, p):
        if n == 1:
            raise RuntimeError("all 7 Groq key(s) are rate limited for 30s")
        return {"sentences": [sentence_for(j)]}
    guard = writer.RateGuard(sleep=sleeps.append)
    (s,), stats = run([j], FakeLLM(reply), rate=guard)
    assert s.origin == ORIGIN_LLM and sleeps == [31.0] and stats["rate_waits"] == 1 and not guard.tripped()


def test_long_rate_limit_trips_the_breaker_and_later_calls_are_skipped():
    js = jobs(1)
    guard = writer.RateGuard(sleep=lambda s: None)

    def reply(n, m, f, p):
        raise RuntimeError("all 7 Groq key(s) are rate limited for 900s")
    llm = FakeLLM(reply)
    (s1,), _ = run(js, llm, rate=guard)
    assert s1.origin == ORIGIN_FALLBACK and guard.tripped()
    (s2,), stats = run(js, llm, rate=guard)
    assert s2.origin == ORIGIN_FALLBACK and len(llm.calls) == 1 and stats["skipped"] == 1       # the second call was not even sent


def test_groq_exhausted_exception_by_name_trips_the_breaker():
    class GroqRateLimitExhausted(Exception):
        pass
    guard = writer.RateGuard(sleep=lambda s: None)
    llm = FakeLLM(lambda *a: (_ for _ in ()).throw(GroqRateLimitExhausted("gave up after 300s of rate limits")))
    run(jobs(1), llm, rate=guard)
    assert guard.tripped()


def test_413_splits_the_call_and_is_not_the_retry():
    js = jobs(4)
    good = answer_all(js)

    def reply(n, m, f, p):
        if len(requested_ids(f)) > 2:
            err = RuntimeError("Request too large for model")
            err.status_code = 413
            raise err
        return good(n, m, f, p)
    llm = FakeLLM(reply)
    sentences, stats = run(js, llm)
    assert all(s.origin == ORIGIN_LLM and s.attempts == 1 for s in sentences)
    assert stats["splits"] == 1 and stats["retried"] == 0 and stats["calls"] == 3 and stats["fallback"] == 0
    assert [requested_ids(c["format"]) for c in llm.calls] == [["j0", "j1", "j2", "j3"], ["j0", "j1"], ["j2", "j3"]]


def test_413_on_a_single_job_falls_back_without_retry():
    def reply(n, m, f, p):
        raise RuntimeError("Error code: 413 - request_too_large")
    llm = FakeLLM(reply)
    (s,), stats = run(jobs(1), llm)
    assert s.origin == ORIGIN_FALLBACK and len(llm.calls) == 1 and stats["retried"] == 0


def test_413_keeps_splitting_down_to_what_fits():
    js = jobs(8)
    good = answer_all(js)

    def reply(n, m, f, p):
        if len(requested_ids(f)) > 1:
            raise RuntimeError("413 Request too large")
        return good(n, m, f, p)
    sentences, stats = run(js, FakeLLM(reply))
    assert all(s.origin == ORIGIN_LLM for s in sentences) and stats["retried"] == 0


def _json_validate_failed(msg="Failed to generate JSON. Please adjust your prompt. See 'failed_generation' for more details."):
    err = RuntimeError("Error code: 400 - " + str({"error": {"message": msg, "type": "invalid_request_error", "code": "json_validate_failed",
                                                  "failed_generation": "max completion tokens reached before generating a valid document"}}))
    err.body = {"error": {"message": msg, "code": "json_validate_failed"}}
    return err


def test_json_validate_failed_splits_the_call_like_a_413_and_nothing_falls_back():
    js = jobs(4)
    good = answer_all(js)

    def reply(n, m, f, p):
        if len(requested_ids(f)) > 2:
            raise _json_validate_failed()                      # the first live run: 'max completion tokens reached before generating a valid document'
        return good(n, m, f, p)
    llm = FakeLLM(reply)
    sentences, stats = run(js, llm)
    assert all(s.origin == ORIGIN_LLM and s.attempts == 1 for s in sentences)
    assert stats["splits"] == 1 and stats["retried"] == 0 and stats["fallback"] == 0 and stats["llm_errors"] == 0 and stats["malformed"] == 1
    assert [requested_ids(c["format"]) for c in llm.calls] == [["j0", "j1", "j2", "j3"], ["j0", "j1"], ["j2", "j3"]]


def test_json_validate_failed_on_a_single_job_is_a_failed_attempt_then_retried():
    def reply(n, m, f, p):
        if n == 1:
            raise _json_validate_failed("Failed to validate JSON. Please adjust your prompt.")
        return answer_all(js)(n, m, f, p)
    js = jobs(1)
    llm = FakeLLM(reply)
    (s,), stats = run(js, llm)
    assert s.origin == ORIGIN_LLM and s.attempts == 2 and len(llm.calls) == 2 and stats["retried"] == 1
    assert "cut off" in s.reasons[0]


def test_json_validate_failed_is_recognised_from_the_body_or_the_text():
    assert writer.is_bad_json(_json_validate_failed())
    assert writer.is_bad_json(RuntimeError("Error code: 400 - {'code': 'json_validate_failed'}"))
    assert not writer.is_bad_json(RuntimeError("Error code: 400 - something else"))


# ------------------------------------------------------------------------------------------------------------ cache
def test_validated_reply_is_cached_and_a_hit_costs_no_call(tmp_path):
    js = jobs(2)
    cache = writer.DiskCache(tmp_path / "c")
    llm = FakeLLM(answer_all(js))
    s1, st1 = run(js, llm, cache=cache)
    assert st1["calls"] == 1 and len(list((tmp_path / "c").glob("*.json"))) == 1
    boom = FakeLLM(lambda *a: (_ for _ in ()).throw(AssertionError("the LLM must not be called on a cache hit")))
    s2, st2 = run(js, boom, cache=cache)
    assert st2["cache_hits"] == 2 and st2["calls"] == 0 and boom.calls == []
    assert [s.text for s in s2] == [s.text for s in s1] and all(s.origin == ORIGIN_LLM for s in s2)


def test_default_cache_follows_the_env(tmp_path, monkeypatch):
    js = jobs(1)
    run(js, FakeLLM(answer_all(js)), cache=None)
    assert list((tmp_path / "s5cache").glob("*.json"))
    monkeypatch.setenv("STAGE5_CACHE", "false")
    assert writer.resolve_cache(None) is None and writer.resolve_cache(False) is None


def test_cache_hit_is_validated_again():
    js = jobs(1)
    store = {}

    class MemCache:
        def get(self, k):
            return store.get(k)

        def put(self, k, v):
            store[k] = v
    cache = MemCache()
    run(js, FakeLLM(answer_all(js)), cache=cache)
    assert len(store) == 1
    llm = FakeLLM(answer_all(js))
    seen = []

    def stricter(t, ids, j):
        seen.append(t)
        return ["a new rule rejects it"] if len(seen) == 1 else []         # the cached sentence now fails; the fresh one passes
    (s,), stats = run(js, llm, cache=cache, check=stricter)
    assert len(llm.calls) == 1 and stats["cache_hits"] == 0 and s.origin == ORIGIN_LLM


def test_failures_are_never_cached(tmp_path):
    js = jobs(2)
    cache = writer.DiskCache(tmp_path / "c")
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(js[0])]})        # j1 is never answered
    sentences, _ = run(js, llm, cache=cache)
    assert sentences[1].origin == ORIGIN_FALLBACK
    assert not list((tmp_path / "c").glob("*.json"))
    run(js, FakeLLM(lambda *a: (_ for _ in ()).throw(ConnectionError("x"))), cache=cache)
    assert not list((tmp_path / "c").glob("*.json"))


def test_retry_success_is_cached_under_the_first_attempt_prompt(tmp_path):
    j = job("j0", ["c0"])
    cache = writer.DiskCache(tmp_path / "c")
    llm = FakeLLM(lambda n, m, f, p: {"sentences": [sentence_for(j, " BAD" if n == 1 else "")]})
    run([j], llm, cache=cache, check=lambda t, i, jj: ["bad"] if "BAD" in t else [])
    key = writer.cache_key(prompts.write_messages("How does A compare with B?", [j], {}))
    assert cache.get(key)["sentences"][0]["job_id"] == "j0" and "BAD" not in cache.get(key)["sentences"][0]["text"]


def test_cache_key_changes_with_model_and_settings(monkeypatch):
    msgs = prompts.write_messages("S", jobs(1), {})
    base = writer.cache_key(msgs)
    assert writer.cache_key(msgs) == base
    monkeypatch.setenv("STAGE5_MODEL", "other/model")
    assert writer.cache_key(msgs) != base
    monkeypatch.delenv("STAGE5_MODEL")
    monkeypatch.setenv("STAGE5_MAX_OUTPUT_TOKENS", "999")
    assert writer.cache_key(msgs) != base
    monkeypatch.delenv("STAGE5_MAX_OUTPUT_TOKENS")
    monkeypatch.setenv("STAGE5_REASONING_EFFORT", "high")
    assert writer.cache_key(msgs) != base
    monkeypatch.delenv("STAGE5_REASONING_EFFORT")
    assert writer.cache_key(prompts.write_messages("S", [job("j0", ["c0"], quote="a different quote")], {})) != base


def test_unreadable_cache_entry_is_a_miss(tmp_path):
    js = jobs(1)
    cache = writer.DiskCache(tmp_path / "c")
    key = writer.cache_key(prompts.write_messages("How does A compare with B?", js, {}))
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / f"{key}.json").write_text("{not json", encoding="utf-8")
    llm = FakeLLM(answer_all(js))
    (s,), stats = run(js, llm, cache=cache)
    assert s.origin == ORIGIN_LLM and stats["calls"] == 1 and stats["cache_hits"] == 0


# ------------------------------------------------------------------------------------------------------------ never raises, progress, threads
def test_progress_errors_never_reach_the_caller_and_events_are_sent():
    events = []

    def progress(step, message, **data):
        events.append((step, data))
        raise RuntimeError("sink broke")
    js = jobs(2)
    sentences, _ = run(js, FakeLLM(answer_all(js)), progress=progress)
    assert len(sentences) == 2 and events and events[0][0] == "write" and events[0][1]["jobs"] == 2


def test_write_section_never_raises_even_when_everything_is_broken():
    class Broken:
        def get(self, k):
            raise OSError("disk")

        def put(self, k, v):
            raise OSError("disk")
    j = job("j0", ["c0"])
    (s,), _ = run([j], lambda *a: 1 / 0, cache=Broken(), check=lambda *a: 1 / 0, fallback=lambda jj: 1 / 0)
    assert s.origin == ORIGIN_FALLBACK and s.text


def test_parallel_sections_are_thread_safe_and_ordered():
    sections = [(f"Section {k}", [job(f"s{k}_j{i}", [f"s{k}_c{i}"]) for i in range(3)]) for k in range(9)]
    every = [j for _, js in sections for j in js]
    llm = FakeLLM(answer_all(every), delay=0.02)
    out = writer.write_sections(sections, workers=4, llm=llm, check=ok_check, fallback=fb, cache=False, tier_rules={})
    assert len(out) == 9 and 1 < llm.peak <= 4
    for (title, js), (sentences, stats) in zip(sections, out):
        assert [s.job_id for s in sentences] == [j.job_id for j in js]
        assert all(s.origin == ORIGIN_LLM for s in sentences) and stats["calls"] == 1
    assert len(llm.calls) == 9
    total = writer.merge_stats(*[st for _, st in out])
    assert total["jobs"] == 27 and total["calls"] == 9 and total["llm_sentences"] == 27


def test_parallel_sections_with_a_shared_disk_cache(tmp_path):
    sections = [("Same section", [job("j0", ["c0"])]) for _ in range(6)]       # the same key from several threads at once
    llm = FakeLLM(answer_all([job("j0", ["c0"])]), delay=0.01)
    out = writer.write_sections(sections, workers=3, llm=llm, check=ok_check, fallback=fb, cache=writer.DiskCache(tmp_path / "c"), tier_rules={})
    assert all(s[0].origin == ORIGIN_LLM for s, _ in out)
    assert len(list((tmp_path / "c").glob("*.json"))) == 1 and not list((tmp_path / "c").glob("*.tmp"))


def test_write_sections_single_worker_matches_sequential():
    sections = [(f"S{k}", jobs(2)) for k in range(3)]
    llm = FakeLLM(answer_all(jobs(2)))
    out = writer.write_sections(sections, workers=1, llm=llm, check=ok_check, fallback=fb, cache=False, tier_rules={})
    assert len(out) == 3 and len(llm.calls) == 3


# ------------------------------------------------------------------------------------------------------------ default llm and default check
def test_default_llm_passes_the_strict_schema_effort_and_token_cap(monkeypatch):
    from apps.api.services import groq_pool
    captured = {}

    class Resp:
        usage = types.SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content='```json\n{"sentences": []}\n```'))]

    def fake_chat(**kw):
        captured.update(kw)
        return Resp()
    monkeypatch.setattr(groq_pool, "chat", fake_chat)
    monkeypatch.setenv("STAGE5_MAX_OUTPUT_TOKENS", "1234")
    fmt = prompts.section_schema(jobs(1))
    data, usage = writer.default_llm([{"role": "user", "content": "hi"}], fmt, "stage5_write")
    assert data == {"sentences": []} and usage == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    assert captured["model"] == "openai/gpt-oss-120b" and captured["purpose"] == "stage5_write" and captured["response_format"] is fmt
    assert captured["max_completion_tokens"] == 1234 and captured["reasoning_effort"] == "low" and captured["temperature"] == 0.2


def test_default_llm_is_used_when_none_is_injected(monkeypatch):
    from apps.api.services import groq_pool
    j = job("j0", ["c0"])

    class Resp:
        usage = None
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=json.dumps({"sentences": [sentence_for(j)]})))]
    monkeypatch.setattr(groq_pool, "chat", lambda **kw: Resp())
    (s,), stats = writer.write_section("S", [j], check=ok_check, fallback=fb, cache=False, tier_rules={})
    assert s.origin == ORIGIN_LLM and stats["calls"] == 1


def test_default_llm_bad_json_is_a_malformed_reply(monkeypatch):
    from apps.api.services import groq_pool

    class Resp:
        usage = None
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content="Sorry, I cannot do that."))]
    monkeypatch.setattr(groq_pool, "chat", lambda **kw: Resp())
    (s,), stats = writer.write_section("S", [job("j0", ["c0"])], check=ok_check, fallback=fb, cache=False, tier_rules={})
    assert s.origin == ORIGIN_FALLBACK and stats["malformed"] == 2


def _install(monkeypatch, name, **attrs):
    mod = types.ModuleType(f"apps.api.agents.stage5_report.{name}")
    for k, v in attrs.items():
        setattr(mod, k, v)
    import apps.api.agents.stage5_report as pkg
    monkeypatch.setitem(sys.modules, mod.__name__, mod)
    monkeypatch.setattr(pkg, name, mod, raising=False)
    return mod


def test_default_check_composes_validators_then_grounding(monkeypatch):
    calls = []
    _install(monkeypatch, "validators", check_sentence=lambda t, ids, j: calls.append("v") or (["a number is new"] if "NEW" in t else []))

    def entails(t, ev, **kw):
        calls.append(("g", ev))
        return (False, {}) if "NLI" in t else (True, {})
    _install(monkeypatch, "grounding", entails=entails)
    j = job("j0", ["c0", "c1"])
    assert writer.default_check("fine", ["c0"], j) == []
    assert writer.default_check("NEW thing", ["c0"], j) == ["a number is new"]
    assert calls.count("v") == 2 and [c for c in calls if isinstance(c, tuple)] == [("g", ["Model A gains 12 points on task c0.", "verbatim quote of c0"])]
    why = writer.default_check("NLI fails", ["c0"], j)
    assert why and "not entailed" in why[0]


def test_default_check_fails_closed_when_a_module_is_broken(monkeypatch):
    _install(monkeypatch, "validators", check_sentence=lambda t, ids, j: [])

    def boom(*a, **k):
        raise RuntimeError("model could not load")
    _install(monkeypatch, "grounding", entails=boom)
    reasons = writer.default_check("fine", ["c0"], job("j0", ["c0"]))
    assert reasons and "could not run" in reasons[0]


def test_grounding_premises_are_the_named_claims_text_and_quotes(monkeypatch):
    got = {}
    _install(monkeypatch, "validators", check_sentence=lambda t, ids, j: [])
    _install(monkeypatch, "grounding", entails=lambda t, ev, **kw: got.update(ev=ev) or (True, {}))
    j = job("j0", ["c0", "c1"])
    writer.default_check("fine", ["c1"], j)
    assert got["ev"] == ["Model A gains 12 points on task c1.", "verbatim quote of c1"]


# ------------------------------------------------------------------------------------------------------------ summary and conclusion
def body(tiers):
    return [Sentence(text=f"Body sentence {i} about topic {i}.", claim_ids=[f"c{i}"], job_id=f"j{i}", tier=t) for i, t in enumerate(tiers)]


def summary_reply(*groups):
    def reply(n, m, f, p):
        return {"sentences": [{"text": f"Summary sentence {k}.", "from_sentences": list(g)} for k, g in enumerate(groups, start=1)]}
    return reply


def srun(fn, sentences, llm, **kw):
    kw.setdefault("check_summary", lambda s, b: [])
    kw.setdefault("cache", False)
    return fn(sentences, llm=llm, **kw)


TIERS8 = [TIER_SINGLE, TIER_SUPPORTED, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED, TIER_SINGLE, TIER_PARTLY, TIER_SINGLE]


def test_select_body_prefers_higher_tiers_and_keeps_report_order():
    sel = summary.select_body(body(TIERS8), limit=4)
    assert [b["job_id"] for b in sel] == ["j1", "j2", "j4", "j6"] and [b["n"] for b in sel] == [1, 2, 3, 4]
    assert all(set(b) >= {"n", "text", "tier", "claim_ids", "job_id"} for b in sel)
    assert summary.select_body([]) == []


def test_summary_happy_path_computes_claim_ids_and_the_weakest_tier():
    seen = {}

    def check(s, b):
        seen["summary"], seen["body"] = s, b
        return []
    llm = FakeLLM(summary_reply([1, 2], [3], [4, 5]))
    sents, stats = srun(summary.write_summary, body(TIERS8), llm, check_summary=check)
    assert len(sents) == 3 and all(s.origin == ORIGIN_LLM and s.attempts == 1 for s in sents)
    assert sents[0].claim_ids == ["c0", "c1"] and sents[0].tier == TIER_SINGLE         # body 1 = single, body 2 = supported -> single
    assert [s.job_id for s in sents] == ["summary_1", "summary_2", "summary_3"]
    assert seen["summary"][0] == {"text": "Summary sentence 1.", "from_sentences": [1, 2]} and seen["body"][0]["n"] == 1
    assert llm.calls[0]["purpose"] == "stage5_summary" and stats["calls"] == 1 and stats["fallback"] == 0


def test_summary_only_ever_sees_the_numbered_sentences():
    llm = FakeLLM(summary_reply([1], [2], [3]))
    srun(summary.write_summary, body(TIERS8), llm)
    content = llm.calls[0]["messages"][1]["content"]
    assert "Body sentence 1 about topic 1." in content and "claim" not in content.lower().replace("claims", "")      # no claim ids, no quotes


def test_summary_retry_with_reasons_then_accepted():
    state = {"n": 0}

    def check(s, b):
        state["n"] += 1
        return ["the number 40 is not in the body"] if state["n"] == 1 else []
    llm = FakeLLM(summary_reply([1], [2], [3]))
    sents, stats = srun(summary.write_summary, body(TIERS8), llm, check_summary=check)
    assert len(llm.calls) == 2 and "the number 40 is not in the body" in llm.calls[1]["messages"][1]["content"]
    assert all(s.attempts == 2 for s in sents) and stats["retried"] == 1 and stats["fallback"] == 0


def test_summary_failing_twice_uses_the_extractive_template_with_no_new_text():
    b = body(TIERS8)
    llm = FakeLLM(summary_reply([1], [2], [3]))
    sents, stats = srun(summary.write_summary, b, llm, check_summary=lambda s, bb: ["stronger than its source"])
    assert len(llm.calls) == 2 and stats["fallback"] == 1
    texts = {s.text for s in b}
    assert len(sents) == 4 and all(s.text in texts and s.origin == ORIGIN_FALLBACK for s in sents)        # verbatim body sentences only
    assert sorted(s.tier for s in sents) == sorted([TIER_SUPPORTED, TIER_SUPPORTED, TIER_PARTLY, TIER_PARTLY])         # the 4 highest tiers are picked
    assert sents[0].reasons == ["stronger than its source", "stronger than its source"]
    assert [s.text for s in sents] == sorted([s.text for s in sents], key=lambda t: int(t.split()[2]))   # report order


def test_summary_malformed_json_then_ok_and_malformed_twice():
    def flaky(n, m, f, p):
        if n == 1:
            raise json.JSONDecodeError("x", "{", 1)
        return summary_reply([1], [2], [3])(n, m, f, p)
    sents, stats = srun(summary.write_summary, body(TIERS8), FakeLLM(flaky))
    assert sents[0].origin == ORIGIN_LLM and stats["malformed"] == 1
    sents2, stats2 = srun(summary.write_summary, body(TIERS8), FakeLLM(lambda *a: {"oops": 1}))
    assert sents2[0].origin == ORIGIN_FALLBACK and stats2["fallback"] == 1


def test_summary_llm_error_goes_straight_to_the_template():
    llm = FakeLLM(lambda *a: (_ for _ in ()).throw(ConnectionError("down")))
    sents, stats = srun(summary.write_summary, body(TIERS8), llm)
    assert len(llm.calls) == 1 and all(s.origin == ORIGIN_FALLBACK for s in sents) and stats["llm_errors"] == 1


@pytest.mark.parametrize("answer,needle", [
    ([{"text": "A.", "from_sentences": [99]}] * 3, "do not exist"),
    ([{"text": "A.", "from_sentences": []}] * 3, "from_sentences"),
    ([{"text": "", "from_sentences": [1]}] * 3, "is empty"),
    ([{"text": "A.", "from_sentences": [1]}], "between 3 and 5"),
    ([{"text": "A.", "from_sentences": [1]}] * 6, "between 3 and 5"),
])
def test_summary_shape_and_length_rules(answer, needle):
    llm = FakeLLM(lambda *a: {"sentences": answer})
    sents, _ = srun(summary.write_summary, body(TIERS8), llm)
    assert sents[0].origin == ORIGIN_FALLBACK and needle in sents[0].reasons[0]


def test_summary_check_that_raises_fails_closed():
    def boom(s, b):
        raise RuntimeError("x")
    sents, _ = srun(summary.write_summary, body(TIERS8), FakeLLM(summary_reply([1], [2], [3])), check_summary=boom)
    assert sents[0].origin == ORIGIN_FALLBACK


def test_too_few_sentences_are_copied_without_an_llm_call():
    llm = FakeLLM(lambda *a: (_ for _ in ()).throw(AssertionError("no call expected")))
    sents, stats = srun(summary.write_summary, body([TIER_SUPPORTED, TIER_SINGLE]), llm)
    assert llm.calls == [] and [s.origin for s in sents] == [ORIGIN_TEMPLATE] * 2 and stats["extractive"] == 1 and stats["calls"] == 0
    assert sents[0].text == "Body sentence 0 about topic 0."


def test_no_sentences_gives_nothing():
    sents, stats = srun(summary.write_summary, [], FakeLLM(lambda *a: {}))
    assert sents == [] and stats["skipped"] == 1


def test_conclusion_has_its_own_range_and_wording():
    seen = {}

    def check(s, b):
        seen["n"] = len(s)
        return []
    llm = FakeLLM(summary_reply([1], [2], [3], [4]))
    sents, _ = srun(summary.write_conclusion, body(TIERS8), llm, check_summary=check)
    assert len(sents) == 4 and sents[0].job_id == "conclusion_1" and "3 to 4 sentences" in llm.calls[0]["messages"][0]["content"]
    five = FakeLLM(summary_reply([1], [2], [3], [4], [5]))
    sents5, _ = srun(summary.write_conclusion, body(TIERS8), five)
    assert sents5[0].origin == ORIGIN_FALLBACK and len(sents5) == 3                  # 5 is too many for a conclusion


def test_summary_cache_hit_is_validated_again_and_failures_not_cached(tmp_path):
    cache = writer.DiskCache(tmp_path / "c")
    b = body(TIERS8)
    llm = FakeLLM(summary_reply([1], [2], [3]))
    srun(summary.write_summary, b, llm, cache=cache)
    assert len(list((tmp_path / "c").glob("*.json"))) == 1
    boom = FakeLLM(lambda *a: (_ for _ in ()).throw(AssertionError("cache hit expected")))
    sents, stats = srun(summary.write_summary, b, boom, cache=cache)
    assert stats["cache_hits"] == 1 and boom.calls == [] and len(sents) == 3
    again = FakeLLM(summary_reply([1], [2], [3]))
    srun(summary.write_summary, b, again, cache=cache, check_summary=lambda s, bb: ["stricter now"])      # re-validated: the hit is refused
    assert len(again.calls) == 2
    fresh = writer.DiskCache(tmp_path / "d")
    srun(summary.write_summary, b, FakeLLM(summary_reply([1], [2], [3])), cache=fresh, check_summary=lambda s, bb: ["no"])
    assert not list((tmp_path / "d").glob("*.json"))


def test_default_check_summary_fails_closed_without_validators(monkeypatch):
    def boom(s, b):
        raise ImportError("missing")
    _install(monkeypatch, "validators", check_summary=boom)
    reasons = summary.default_check_summary([{"text": "x", "from_sentences": [1]}], [])
    assert reasons and "could not run" in reasons[0]
    _install(monkeypatch, "validators", check_summary=lambda s, b: ["number 5 not in body"])
    assert summary.default_check_summary([], []) == ["number 5 not in body"]


def test_summary_uses_the_default_llm_when_none_is_injected(monkeypatch):
    from apps.api.services import groq_pool

    class Resp:
        usage = types.SimpleNamespace(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=json.dumps(
            {"sentences": [{"text": "S1.", "from_sentences": [1]}, {"text": "S2.", "from_sentences": [2]}, {"text": "S3.", "from_sentences": [3]}]})))]
    seen = {}
    monkeypatch.setattr(groq_pool, "chat", lambda **kw: seen.update(kw) or Resp())
    sents, stats = summary.write_summary(body(TIERS8), check_summary=lambda s, b: [], cache=False)
    assert len(sents) == 3 and seen["purpose"] == "stage5_summary" and stats["total_tokens"] == 10


def test_summary_rate_breaker_makes_the_template_at_once():
    guard = writer.RateGuard(sleep=lambda s: None)
    llm = FakeLLM(lambda *a: (_ for _ in ()).throw(RuntimeError("all 7 Groq key(s) are rate limited for 900s")))
    summary.write_summary(body(TIERS8), llm=llm, check_summary=lambda s, b: [], cache=False, rate=guard)
    sents, stats = summary.write_conclusion(body(TIERS8), llm=llm, check_summary=lambda s, b: [], cache=False, rate=guard)
    assert len(llm.calls) == 1 and stats["skipped"] == 1 and all(s.origin == ORIGIN_FALLBACK for s in sents)
