"""Offline tests of the Stage 5 checks: hedging.py, validators.py, grounding.py. Fakes only: no model, no network, no Groq."""
import subprocess
import sys

import pytest

from apps.api.agents.stage5_report import grounding, hedging, validators
from apps.api.agents.stage5_report.schema import Claim, Evidence, Job, Sentence

# ------------------------------------------------------------------------------------------------------------------ builders
VIT_CLAIM = "ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch."
VIT_QUOTE = ("In our experiments, ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k with 300 epochs of training from scratch, "
             "while ResNet-50 reaches 76.1%.")


def mk_claim(cid="c_1", text=VIT_CLAIM, quotes=(VIT_QUOTE,), support_docs=1, label="unverified", near=None):
    ev = [Evidence(source_id="s1", title="Paper A", quote=q, relation="supports", ref_key="paper a") for q in quotes]
    if near:
        ev.append(Evidence(source_id="s2", title="Paper B", quote="other quote", relation="near_match", ref_key="paper b", near_claim=near))
    return Claim(claim_id=cid, sub_question_id="sq1", text=text, label=label, tier=None, support_docs=support_docs, evidence=ev)


def mk_job(tier="single", claims=None):
    return Job(job_id="j1", section_id="sq1", tier=tier, claims=claims or [mk_claim()])


def check(text, tier="single", claims=None, ids=None):
    job = mk_job(tier, claims)
    return validators.check_sentence(text, ids if ids is not None else [c.claim_id for c in job.claims], job)


def vals(text):
    return sorted((round(v, 6), u) for v, u, _ in validators.numbers_in(text))


# ------------------------------------------------------------------------------------------------------------------ import hygiene
def test_importing_the_modules_loads_no_model():
    code = ("import sys; import apps.api.agents.stage5_report.hedging, apps.api.agents.stage5_report.validators, apps.api.agents.stage5_report.grounding;"
            "bad=[m for m in ('sentence_transformers','torch','transformers','apps.api.agents.stage4_factcheck.common','apps.api.services.groq_pool') if m in sys.modules];"
            "print('LOADED', bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120).stdout
    assert "LOADED []" in out, out


# ------------------------------------------------------------------------------------------------------------------ numbers
@pytest.mark.parametrize("a,b", [
    ("1,000 samples", "1000 samples"), ("1k samples", "1,000 samples"), ("1 thousand samples", "1000 samples"), ("one thousand samples", "1k samples"),
    ("12.5%", "12.5 percent"), ("12.5 per cent", "12.5%"), ("12.50%", "12.5 %"), ("three layers", "3 layers"), ("twenty-five heads", "25 heads"),
    ("two hundred epochs", "200 epochs"), ("7B parameters", "7 billion parameters"), ("1.2M images", "1,200,000 images"),
    ("5 ms", "5 milliseconds"), ("12 GB", "12 gigabytes"), ("3x faster", "3 times faster"),
])
def test_number_normalisation_equal(a, b):
    assert vals(a) == vals(b)


def test_number_ranges_take_the_unit_on_both_ends():
    assert vals("3-5%") == [(3.0, "%"), (5.0, "%")]
    assert vals("3 to 5 ms") == [(3.0, "ms"), (5.0, "ms")]
    assert vals("between 2020-2021") == [(2020.0, ""), (2021.0, "")]


def test_percent_points_and_percent_are_different_units():
    assert vals("12.5 percentage points") == [(12.5, "pp")]
    assert vals("12.5 percentage points") != vals("12.5%")


def test_names_do_not_yield_numbers():
    assert vals("ViT-B/16 and ResNet-50 on ImageNet-1k with GPT-4o and T5, top-5 results") == []


def test_number_words_and_the_word_one():
    assert vals("one study reports that no one knows") == []              # pronoun, not a number
    assert vals("one of the models") == []
    assert vals("one dataset was used") == [(1.0, "")]
    assert vals("zero-shot transfer") == [(0.0, "")]
    assert vals("two sources report that the model has four layers") == [(4.0, "")]   # the number of sources is wording, not a measurement


def test_number_edge_forms():
    assert vals("a learning rate of 1e-4") == [(0.0001, "")]
    assert vals("a drop of -5 points") == [(-5.0, "")]
    assert vals("reached 224x224 pixels") == [(224.0, "")]
    assert vals("in 2021") == [(2021.0, "")]


def test_unit_mismatch_is_caught():
    claim = mk_claim(text="Latency is 5 ms per image on the GPU.", quotes=("The latency is 5 ms per image.",))
    assert check("One study reports that latency is 5 ms per image on the GPU.", claims=[claim]) == []
    assert check("One study reports that latency is 5 milliseconds per image on the GPU.", claims=[claim]) == []
    r = check("One study reports that latency is 5 seconds per image on the GPU.", claims=[claim])
    assert any("unit" in x or "5 seconds" in x for x in r), r


def test_derived_and_rounded_numbers_rejected():
    r = check("One study reports that ViT-B/16 reaches about 78% top-1 accuracy on ImageNet-1k.")
    assert any("'78%'" in x for x in r), r
    r = check("One study reports that ViT-B/16 beats ResNet-50 by 1.8 points on ImageNet-1k.")
    assert any("1.8" in x for x in r), r
    r = check("One study reports that ViT-B/16 reaches twice the accuracy of ResNet-50 on ImageNet-1k.")
    assert any("twice" in x for x in r), r


def test_bounds_must_be_in_the_claims():
    claim = mk_claim(text="Training takes up to 300 epochs.", quotes=("Training takes up to 300 epochs on TPUs.",))
    assert check("One study reports that training takes up to 300 epochs.", claims=[claim]) == []
    r = check("One study reports that training takes at least 300 epochs.", claims=[claim])
    assert any("lower bound" in x for x in r), r


# ------------------------------------------------------------------------------------------------------------------ names and entities
def test_entities_found():
    ents = {k for _, k, _ in validators.entities_in("One study reports that ViT-B/16 beats ResNet-50 on ImageNet-1k, and CNNs lag Google's BERT.")}
    assert {"vitb16", "resnet50", "imagenet1k", "cnn", "google", "bert"} <= ents
    assert validators.entities_in("Transformers need more data") == []              # first word is only a capital of the sentence


def test_faithful_paraphrase_passes():
    assert check("One study reports that ViT-B/16 attains 77.9% top-1 accuracy on ImageNet-1k when trained from scratch.") == []
    assert check("One source reports that when trained from scratch, ViT-B/16 reaches a top-1 accuracy of 77.9% on ImageNet-1k.") == []


def test_model_names_with_compounds_and_spacing():
    claim = mk_claim(text="ViT B/16 outperforms ResNet-50 on ImageNet 1k.", quotes=())
    # spacing differences in the evidence do not matter, a different variant does
    assert check("One study reports that ViT-B/16 outperforms ResNet-50 on ImageNet-1k.", claims=[claim]) == []
    r = check("One study reports that ViT-B/32 outperforms ResNet-50 on ImageNet-1k.", claims=[claim])
    assert any("ViT-B/32" in x for x in r), r
    r = check("One study reports that ViT-B/16 outperforms ResNet-101 on ImageNet-1k.", claims=[claim])
    assert any("ResNet-101" in x for x in r), r


def test_acronym_must_be_in_claims_but_plural_is_light_stemmed():
    claim = mk_claim(text="CNN models need less data than Transformer models.", quotes=())
    assert check("One study reports that CNNs need less data than Transformers.", claims=[claim]) == []
    r = check("One study reports that RNNs need less data than Transformers.", claims=[claim])
    assert any("RNNs" in x for x in r), r


def test_roberta_is_not_bert():
    claim = mk_claim(text="RoBERTa improves GLUE scores over its baseline.", quotes=())
    r = check("One study reports that BERT improves GLUE scores over its baseline.", claims=[claim])
    assert any("BERT" in x for x in r), r


# ------------------------------------------------------------------------------------------------------------------ the corrupted-copy test set
CORRUPTIONS = {
    "swapped_number": "One study reports that ViT-B/16 reaches 79.9% top-1 accuracy on ImageNet-1k when trained from scratch.",
    "added_negation": "One study reports that ViT-B/16 does not reach 77.9% top-1 accuracy on ImageNet-1k when trained from scratch.",
    "swapped_entity": "One study reports that ViT-L/16 reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch.",
    "swapped_dataset": "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on CIFAR-100 when trained from scratch.",
    "swapped_capitalised_word": "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch on Google hardware.",
    "added_scope_word": "One study reports that ViT-B/16 always reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch.",
}


@pytest.mark.parametrize("name", sorted(CORRUPTIONS))
def test_corrupted_copies_are_each_caught(name):
    assert check(CORRUPTIONS[name]) != [], name


def test_known_limit_a_number_moved_to_the_wrong_subject_is_left_to_the_models():
    # 76.1% is ResNet-50's figure in the SAME quote; the lexical layer sees a number that exists, so only NLI / the judge can reject this
    wrong = "One study reports that ViT-B/16 reaches 76.1% top-1 accuracy on ImageNet-1k when trained from scratch."
    assert check(wrong) == []
    chk = grounding.make_check(nli=FakeNli(ent=0.0, con=0.9), judge=FakeJudge())
    assert chk(wrong, ["c_1"], mk_job("single"))


def test_dropped_negation_and_reversed_direction_are_caught():
    claim = mk_claim(text="Adding dropout does not improve accuracy on CIFAR-10.", quotes=())
    assert check("One study reports that adding dropout does not improve accuracy on CIFAR-10.", claims=[claim]) == []
    assert check("One study reports that adding dropout fails to improve accuracy on CIFAR-10.", claims=[claim]) == []   # a paraphrased negation
    r = check("One study reports that adding dropout improves accuracy on CIFAR-10.", claims=[claim])
    assert any("negation" in x for x in r), r
    claim2 = mk_claim(text="Model A is faster than model B on CPU.", quotes=())
    assert check("One study reports that model A is faster than model B on CPU.", claims=[claim2]) == []
    r = check("One study reports that model A is slower than model B on CPU.", claims=[claim2])
    assert any("direction" in x for x in r), r


def test_a_number_from_an_uncited_claim_is_caught():
    c1 = mk_claim("c_1", "ViT-B/16 reaches 77.9% top-1 accuracy.", quotes=())
    c2 = mk_claim("c_2", "ResNet-50 reaches 76.1% top-1 accuracy.", quotes=())
    job = mk_job("single", [c1, c2])
    ok = validators.check_sentence("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy.", ["c_1"], job)
    assert ok == []
    bad = validators.check_sentence("One study reports that ViT-B/16 reaches 76.1% top-1 accuracy.", ["c_1"], job)
    assert any("76.1" in x for x in bad), bad


# ------------------------------------------------------------------------------------------------------------------ ids, text hygiene
def test_claim_ids_rules():
    job = mk_job("single", [mk_claim("c_1"), mk_claim("c_2", "ViT-B/16 is trained from scratch.", quotes=())])
    s = "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k."
    assert validators.check_sentence(s, ["c_1"], job) == []
    assert validators.check_sentence(s, ["c_1", "c_2"], job) == []
    assert any("no claim id" in r for r in validators.check_sentence(s, [], job))
    assert any("do not belong" in r for r in validators.check_sentence(s, ["c_9"], job))
    assert any("do not belong" in r for r in validators.check_sentence(s, ["c_1", "c_x"], job))
    assert any("not allowed" in r for r in validators.check_sentence(s, ["c_1"], job, allowed_ids=["c_2"]))
    assert any("no claim id" in r for r in validators.check_sentence(s, None, job))


@pytest.mark.parametrize("bad,needle", [
    ("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k (https://arxiv.org/abs/2010.11929).", "URL"),
    ("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k, see arxiv.org.", "URL"),
    ("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k [1].", "square brackets"),
    ("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k [1, 3].", "square brackets"),
    ("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k (Dosovitskiy et al., 2021).", "author"),
    ("Dosovitskiy et al. report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "author"),
    ("Smith and Jones (2020) report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "author"),
    ("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k (doi:10.1000/xyz).", "URL"),
    ("One study reports c_1a2b3c4d5e that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "claim id"),
])
def test_no_url_bracket_author_year(bad, needle):
    r = check(bad)
    assert any(needle in x for x in r), r


@pytest.mark.parametrize("bad", [
    "Therefore, ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch.",
    "One study reports that ViT-B/16 thus reaches 77.9% top-1 accuracy on ImageNet-1k.",
    "Overall, one study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.",
    "One study reports ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k, which suggests that it generalises.",
    "One study reports ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k, as a result it is strong.",
    "However, one study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.",
])
def test_banned_connectives(bad):
    r = check(bad)
    assert any("synthesis wording" in x or "stand alone" in x for x in r), r


def test_connective_in_the_claim_wording_is_tolerated():
    claim = mk_claim(text="Overall accuracy is 77.9% on ImageNet-1k.", quotes=())
    assert check("One study reports that overall accuracy is 77.9% on ImageNet-1k.", claims=[claim]) == []


def test_length_and_one_sentence():
    long_text = "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k " + " ".join(["from scratch"] * 40) + "."
    assert any("too long" in x and "shorten it to about 50 words" in x for x in check(long_text))      # the retry prompt says what to aim for
    two = "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy. It is trained from scratch on ImageNet-1k."
    assert any("exactly one sentence" in x for x in check(two))
    assert any("too short" in x for x in check("One study reports."))
    assert any("empty" in x for x in check("   "))
    assert any("formatting" in x for x in check("One study reports that ViT-B/16 reaches **77.9%** top-1 accuracy on ImageNet-1k."))
    assert check("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k, e.g. when trained from scratch.") == []


def test_word_limit_env(monkeypatch):
    monkeypatch.setenv("STAGE5_MAX_SENTENCE_WORDS", "12")
    assert any("too long" in x for x in check("One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch."))


# ------------------------------------------------------------------------------------------------------------------ hedging per tier
@pytest.mark.parametrize("tier", ["single", "partly"])
@pytest.mark.parametrize("verb", ["shows", "proves", "demonstrates", "confirms", "establishes"])
def test_forbidden_verbs_for_single_and_partly(tier, verb):
    text = f"One study {verb} that ViT-B/16 reaches 77.9% top-1 accuracy" + (", while another makes a related point." if tier == "partly" else ".")
    r = hedging.check_hedge(tier, text)
    assert any(f"'{verb}'" in x for x in r), r


def test_single_requires_an_opener():
    assert hedging.check_hedge("single", "One study reports that X is faster.") == []
    assert hedging.check_hedge("single", "According to one source, X is faster.") == []
    assert hedging.check_hedge("single", "A single paper finds that X is faster.") == []
    assert hedging.check_hedge("single", "One recent study reports that X is faster.") == []
    assert any("must open" in x for x in hedging.check_hedge("single", "X is faster than Y."))
    assert any("must open" in x for x in hedging.check_hedge("single", "Studies report that X is faster."))
    assert any("one source" in x for x in hedging.check_hedge("single", "One study reports that two studies agree that X is faster."))
    assert any("one source" in x for x in hedging.check_hedge("single", "One study reports that X is faster, and other studies agree."))


def test_partly_requires_opener_and_a_related_marker():
    ok = "One source reports that X lowers latency, while another makes a related point that Y lowers cost."
    assert hedging.check_hedge("partly", ok) == []
    assert any("related" in x for x in hedging.check_hedge("partly", "One source reports that X lowers latency."))
    assert any("must open" in x for x in hedging.check_hedge("partly", "X lowers latency, while another makes a related point."))


def test_supported_has_light_rules():
    assert hedging.check_hedge("supported", "Two sources report that X is faster.") == []
    assert hedging.check_hedge("supported", "X is faster than Y.") == []
    assert hedging.check_hedge("supported", "Several sources show that X is faster.") == []
    assert any("proves" in x for x in hedging.check_hedge("supported", "Two sources report that this proves X is faster."))


def test_disputed_and_unknown_tier():
    assert hedging.check_hedge("disputed", "Anything at all here.")
    assert hedging.check_hedge("bogus", "Anything at all here.")


def test_forbidden_word_in_claim_wording_is_tolerated_but_not_as_the_opening_verb():
    claim = "The method shows lower variance than the baseline."
    assert hedging.check_hedge("single", "One study reports that the method shows lower variance than the baseline.", claim) == []
    assert hedging.check_hedge("single", "One study shows that the method has lower variance than the baseline.", claim)


def test_tier_rules_have_what_the_prompt_needs():
    for t in ("supported", "partly", "single"):
        r = hedging.TIER_RULES[t]
        assert r["instruction"] and r["examples"] and "forbidden_verbs" in r and "opener_patterns" in r
    assert "shows" in hedging.TIER_RULES["single"]["forbidden_verbs"]
    assert hedging.TIER_RULES["single"]["opener_required"] and hedging.TIER_RULES["partly"]["opener_required"]
    assert "disputed" not in hedging.TIER_RULES


def test_sentence_check_applies_the_tier_hedge_and_source_count():
    r = check("ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k when trained from scratch.", tier="single")
    assert any("must open" in x for x in r)
    c = mk_claim(support_docs=2)
    assert check("Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "supported", [c]) == []
    r = check("Three sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "supported", [c])
    assert any("more documents" in x for x in r), r
    # the count of sources is wording: it never trips the number check
    assert check("Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "supported", [mk_claim(support_docs=0)]) == []


# ------------------------------------------------------------------------------------------------------------------ fallback sentences
def test_fallback_sentences_pass_the_hedge_check():
    for tier, near in (("single", None), ("supported", None), ("partly", "ViT reaches about 78% on ImageNet")):
        job = mk_job(tier, [mk_claim(support_docs=2, near=near)])
        text = hedging.fallback_sentence(job)
        assert text.endswith(".") and text.count(".") >= 1
        assert hedging.check_hedge(tier, text, VIT_CLAIM) == [], (tier, text)
    assert hedging.fallback_sentence(mk_job("single")).startswith("One study reports that ViT-B/16 reaches 77.9%")
    assert hedging.fallback_sentence(mk_job("supported", [mk_claim(support_docs=2)])).startswith("Two sources report that ViT-B/16")
    assert hedging.fallback_sentence(mk_job("supported", [mk_claim(support_docs=4)])).startswith("Several sources report that")
    part = hedging.fallback_sentence(mk_job("partly", [mk_claim(near="ViT reaches about 78% on ImageNet")]))
    assert "makes a related point that ViT reaches about 78% on ImageNet" in part


def test_fallback_lowercases_a_common_first_word_but_not_names():
    job = mk_job("single", [mk_claim(text="Larger models need more data.", quotes=())])
    assert "reports that larger models need more data." in hedging.fallback_sentence(job)
    job = mk_job("single", [mk_claim(text="ViT needs more data than CNNs.", quotes=())])
    assert "reports that ViT needs more data than CNNs." in hedging.fallback_sentence(job)
    job = mk_job("single", [mk_claim(text="BERT is large.", quotes=())])
    assert "reports that BERT is large." in hedging.fallback_sentence(job)


def test_fallback_with_several_claims_one_sentence():
    c1, c2 = mk_claim("c_1", "Method A is fast.", quotes=("qa",)), mk_claim("c_2", "Method B is slow.", quotes=("qb",))
    text = hedging.fallback_sentence(mk_job("single", [c1, c2]))
    assert text == "One study reports that Method A is fast; it also reports that Method B is slow."
    c2.evidence[0].ref_key = "paper z"
    assert hedging.fallback_sentence(mk_job("single", [c1, c2])).endswith("another reports that Method B is slow.")
    assert validators.count_sentences(text) == 1


def test_make_fallback_sentence_is_a_schema_sentence():
    s = hedging.make_fallback_sentence(mk_job("single"), ["number x"])
    assert isinstance(s, Sentence) and s.origin == "fallback" and s.attempts == 0 and s.claim_ids == ["c_1"] and s.reasons == ["number x"]


def test_strip_attribution():
    assert hedging.strip_attribution("One study reports that ViT is big.") == "ViT is big."
    assert hedging.strip_attribution("According to one source, ViT is big.") == "ViT is big."
    assert hedging.strip_attribution("Two sources report that ViT is big.") == "ViT is big."
    assert hedging.strip_attribution("ViT is big.") == "ViT is big."


# ------------------------------------------------------------------------------------------------------------------ summary check
def body(*items):
    return [{"text": t, "tier": tier} for t, tier in items]


BODY = body(
    ("Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", "supported"),
    ("One study reports that ResNet-50 reaches 76.1% top-1 accuracy on ImageNet-1k.", "single"),
    ("One source reports that data augmentation helps, while another makes a related point that regularisation helps.", "partly"),
    ("Two sources report that training takes 300 epochs.", "supported"),
)


def summ(*items):
    return [{"text": t, "from_sentences": f} for t, f in items]


GOOD_SUMMARY = summ(
    ("Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", [1]),
    ("One study reports that ResNet-50 reaches 76.1% top-1 accuracy on ImageNet-1k.", [2]),
    ("Two sources report that training takes 300 epochs.", [4]),
)


def test_summary_good_passes():
    assert validators.check_summary(GOOD_SUMMARY, BODY) == []


def test_summary_sentence_count():
    assert any("3 to 5" in r for r in validators.check_summary(GOOD_SUMMARY[:2], BODY))
    six = GOOD_SUMMARY * 2
    assert any("3 to 5" in r for r in validators.check_summary(six, BODY))
    assert validators.check_summary(GOOD_SUMMARY[:1], BODY[:1]) == []        # a body of one sentence needs only one summary sentence
    assert validators.check_summary(GOOD_SUMMARY, []) != []
    assert validators.check_summary(GOOD_SUMMARY[:2], BODY, min_sentences=2, max_sentences=4) == []     # conclusion sizes


def test_summary_new_number_or_entity_rejected():
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[0]["text"] = "Two sources report that ViT-B/16 reaches 80.1% top-1 accuracy on ImageNet-1k."
    assert any("80.1" in r for r in validators.check_summary(s, BODY))
    s[0]["text"] = "Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on CIFAR-100."
    assert any("CIFAR-100" in r for r in validators.check_summary(s, BODY))
    s[0]["text"] = "Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k, matching EfficientNet."
    assert any("EfficientNet" in r for r in validators.check_summary(s, BODY))


def test_summary_number_must_come_from_the_mapped_sentences():
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[0]["from_sentences"] = [2]       # 77.9 is in sentence 1, not in sentence 2
    assert any("77.9" in r for r in validators.check_summary(s, BODY))


def test_summary_hedge_not_stronger_than_weakest_source():
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[1]["text"] = "ResNet-50 reaches 76.1% top-1 accuracy on ImageNet-1k."          # a single-source sentence stated as fact
    assert any("stronger" in r for r in validators.check_summary(s, BODY))
    s[1]["text"] = "Two sources report that ResNet-50 reaches 76.1% top-1 accuracy on ImageNet-1k."
    assert any("stronger" in r for r in validators.check_summary(s, BODY))
    s[1]["text"] = "One study reports that ResNet-50 reaches 76.1% top-1 accuracy on ImageNet-1k."
    assert validators.check_summary(s, BODY) == []
    # mixing a supported and a single sentence: the weakest wins
    s[1] = {"text": "Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy and ResNet-50 reaches 76.1% on ImageNet-1k.", "from_sentences": [1, 2]}
    assert any("stronger" in r for r in validators.check_summary(s, BODY))
    s[1] = {"text": "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy and ResNet-50 reaches 76.1% on ImageNet-1k.", "from_sentences": [1, 2]}
    assert validators.check_summary(s, BODY) == []
    # partly body: the summary may not say "Two sources report"
    p = summ(("Two sources report that data augmentation helps.", [3]), GOOD_SUMMARY[0]["text"] and (GOOD_SUMMARY[0]["text"], [1]), (GOOD_SUMMARY[2]["text"], [4]))
    assert any("stronger" in r for r in validators.check_summary(p, BODY))


def test_summary_from_sentences_mapping():
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[0]["from_sentences"] = []
    assert any("from_sentences" in r for r in validators.check_summary(s, BODY))
    s[0]["from_sentences"] = [9]
    assert any("from_sentences" in r for r in validators.check_summary(s, BODY))
    s[0]["from_sentences"] = ["1"]
    assert validators.check_summary(s, BODY) == []
    del s[0]["from_sentences"]
    assert any("from_sentences" in r for r in validators.check_summary(s, BODY))
    zero = summ(*[(t["text"], [x - 1 for x in t["from_sentences"]]) for t in GOOD_SUMMARY])
    assert validators.check_summary(zero, BODY, index_base=0) == []


def test_summary_text_hygiene_and_connectives():
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[0]["text"] = "Two sources report that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k [1]."
    assert any("square brackets" in r for r in validators.check_summary(s, BODY))
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[2]["text"] = "Overall, two sources report that training takes 300 epochs."
    assert any("synthesis" in r for r in validators.check_summary(s, BODY))
    assert validators.check_summary(s, BODY, allow_connectives=True) == []         # the conclusion may use them


def test_summary_accepts_objects_and_strings():
    from types import SimpleNamespace as NS
    s = [NS(text=t["text"], from_sentences=t["from_sentences"]) for t in GOOD_SUMMARY]
    b = [Sentence(text=t["text"], claim_ids=["c_1"], job_id="j", tier=t["tier"]) for t in BODY]
    assert validators.check_summary(s, b) == []
    assert validators.check_summary(s, [t["text"] for t in BODY]) == []            # tier read from the wording


def test_summary_negation_is_caught():
    s = summ(*[(t["text"], t["from_sentences"]) for t in GOOD_SUMMARY])
    s[0]["text"] = "Two sources report that ViT-B/16 does not reach 77.9% top-1 accuracy on ImageNet-1k."
    assert any("negation" in r for r in validators.check_summary(s, BODY))


# ------------------------------------------------------------------------------------------------------------------ grounding: fall-through logic
class FakeNli:
    def __init__(self, ent=0.0, con=0.0, error=None, fn=None):
        self.ent, self.con, self.error, self.fn, self.calls = ent, con, error, fn, []

    def __call__(self, pairs):
        self.calls.append(list(pairs))
        if self.error:
            raise self.error
        if self.fn:
            return [self.fn(p, h) for p, h in pairs]
        return [{"entailment": self.ent, "contradiction": self.con, "neutral": 1 - self.ent - self.con} for _ in pairs]


class FakeJudge:
    def __init__(self, supports=True, confidence=0.9, error=None, reason="ok"):
        self.v = {"supports": supports, "confidence": confidence, "reason": reason}
        self.error, self.calls = error, []

    def __call__(self, claim, quote):
        self.calls.append((claim, quote))
        if self.error:
            raise self.error
        return dict(self.v)


EV = ["ViT-B/16 reaches 77.9% top-1 accuracy.", "In our experiments ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k."]
SENT = "One study reports that ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k."


def test_nli_accepts_and_judge_is_not_called():
    nli, judge = FakeNli(ent=0.9), FakeJudge()
    ok, d = grounding.entails(SENT, EV, nli=nli, judge=judge)
    assert ok and d["via"] == "nli" and d["entailment"] == 0.9 and judge.calls == []
    assert d["nli_pairs"] == 1 and d["judge_calls"] == 0                # the concatenation is asked first and decided it: one pair, not three
    assert len(nli.calls) == 1 and nli.calls[0][0][0] == " ".join(EV)
    # hypothesis is the content without the attribution
    assert nli.calls[0][0][1] == "ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k."


def test_single_premises_are_asked_one_at_a_time_only_when_the_concatenation_did_not_decide():
    def fn(p, h):
        if p == EV[0]:
            return {"entailment": 0.8, "contradiction": 0.0, "neutral": 0.2}
        return {"entailment": 0.1, "contradiction": 0.0, "neutral": 0.9}
    nli = FakeNli(fn=fn)
    ok, d = grounding.entails(SENT, EV, nli=nli, judge=FakeJudge(False))
    assert ok and d["via"] == "nli" and d["nli_pairs"] == 2             # concatenation (neutral), then the first premise (entails): the second is not asked
    assert [len(c) for c in nli.calls] == [1, 1]


def test_contradiction_of_a_single_premise_still_rejects_when_the_concatenation_is_neutral():
    def fn(p, h):
        if p == EV[1]:
            return {"entailment": 0.0, "contradiction": 0.9, "neutral": 0.1}
        return {"entailment": 0.1, "contradiction": 0.0, "neutral": 0.9}
    judge = FakeJudge()
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(fn=fn), judge=judge)
    assert not ok and "contradicts" in d["reason"] and judge.calls == []


def test_nli_rejects_judge_accepts():
    nli, judge = FakeNli(ent=0.1, con=0.0), FakeJudge(True, 0.8)
    ok, d = grounding.entails(SENT, EV, nli=nli, judge=judge)
    assert ok and d["via"] == "judge" and d["judge_calls"] == 1 and len(judge.calls) == 1
    assert judge.calls[0][0].startswith("ViT-B/16 reaches") and "ImageNet-1k" in judge.calls[0][1]


def test_both_reject_fails_closed():
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.1), judge=FakeJudge(False, 0.9))
    assert not ok and d["via"] is None and "not supported" in d["reason"]
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.1), judge=FakeJudge(True, 0.69))          # below the judge threshold
    assert not ok
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.49), judge=FakeJudge(True, 0.7))          # exactly at the judge threshold is accepted
    assert ok and d["via"] == "judge"


def test_contradiction_is_a_hard_reject_without_asking_the_judge():
    judge = FakeJudge(True, 0.99)
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.0, con=0.8), judge=judge)
    assert not ok and judge.calls == [] and "contradicts" in d["reason"]
    # one contradicting premise among entailing ones still rejects (fail closed)
    nli = FakeNli(fn=lambda p, h: {"entailment": 0.9, "contradiction": 0.0, "neutral": 0.1} if p == EV[0] else {"entailment": 0.0, "contradiction": 0.7, "neutral": 0.3})
    ok, d = grounding.entails(SENT, EV, nli=nli, judge=judge)
    assert not ok and judge.calls == []


def test_judge_failure_fails_closed():
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.0), judge=FakeJudge(error=RuntimeError("boom")))
    assert not ok and "judge_error" in d and "could not be verified" in d["reason"]
    # the real judge_support reports its own failure as a dict (supports False, "judge failed: ..."): also closed
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.0), judge=FakeJudge(False, 0.0, reason="judge failed: 429"))
    assert not ok and "judge_error" in d


def test_nli_failure_falls_to_the_judge_but_never_accepts_unchecked():
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(error=RuntimeError("no model")), judge=FakeJudge(True, 0.9))
    assert ok and d["via"] == "judge" and "nli_error" in d
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(error=RuntimeError("no model")), judge=FakeJudge(False, 0.9))
    assert not ok
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(error=RuntimeError("x")), judge=FakeJudge(error=RuntimeError("y")))
    assert not ok and "nli_error" in d and "judge_error" in d
    bad = FakeNli(fn=None)
    bad.__call__ = None
    ok, d = grounding.entails(SENT, EV, nli=lambda pairs: [], judge=FakeJudge(False))              # wrong number of results
    assert not ok and "nli_error" in d


def test_no_evidence_or_empty_sentence_is_rejected_without_any_call():
    nli, judge = FakeNli(ent=1.0), FakeJudge()
    assert grounding.entails(SENT, [], nli=nli, judge=judge)[0] is False
    assert grounding.entails(SENT, ["", "  "], nli=nli, judge=judge)[0] is False
    assert grounding.entails("   ", EV, nli=nli, judge=judge)[0] is False
    assert nli.calls == [] and judge.calls == []


def test_single_premise_has_no_concatenation_pair_and_limits(monkeypatch):
    nli = FakeNli(ent=0.9)
    grounding.entails(SENT, ["ViT-B/16 reaches 77.9% top-1 accuracy."], nli=nli, judge=FakeJudge())
    assert len(nli.calls) == 1 and len(nli.calls[0]) == 1
    monkeypatch.setenv("STAGE5_NLI_MAX_PREMISES", "2")
    nli = FakeNli(ent=0.0)
    grounding.entails(SENT, [f"premise number {i} about ViT-B/16" for i in range(6)], nli=nli, judge=FakeJudge(False))
    assert len(nli.calls) == 3                                      # the concatenation + 2 premises, one pair per call


def test_thresholds_from_the_environment(monkeypatch):
    monkeypatch.setenv("STAGE5_ENTAIL_MIN", "0.95")
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.9), judge=FakeJudge(False))
    assert not ok
    monkeypatch.setenv("STAGE5_ENTAIL_MIN", "0.5")
    monkeypatch.setenv("STAGE5_CONTRA_MIN", "0.9")
    ok, d = grounding.entails(SENT, EV, nli=FakeNli(ent=0.0, con=0.8), judge=FakeJudge(True, 0.9))
    assert ok and d["via"] == "judge"                                   # contradiction below the raised bar, so the judge decides


def test_stats_counters():
    grounding.reset_stats()
    grounding.entails(SENT, EV, nli=FakeNli(ent=0.9), judge=FakeJudge())
    grounding.entails(SENT, EV, nli=FakeNli(ent=0.0), judge=FakeJudge(True, 0.9))
    grounding.entails(SENT, EV, nli=FakeNli(ent=0.0), judge=FakeJudge(False))
    grounding.entails(SENT, EV, nli=FakeNli(con=0.9), judge=FakeJudge())
    s = grounding.stats()
    assert s["calls"] == 4 and s["accepted_nli"] == 1 and s["accepted_judge"] == 1 and s["rejected"] == 2
    assert s["contradiction_rejects"] == 1 and s["judge_calls"] == 2 and s["nli_pairs"] == 8
    grounding.reset_stats()
    assert grounding.stats() == {}


def test_default_models_are_only_loaded_when_not_injected(monkeypatch):
    called = []
    monkeypatch.setattr(grounding, "_default_nli", lambda: called.append("nli") or FakeNli(ent=0.9))
    monkeypatch.setattr(grounding, "_default_judge", lambda: called.append("judge") or FakeJudge())
    grounding.entails(SENT, EV, nli=FakeNli(ent=0.9))
    assert called == []
    grounding.entails(SENT, EV)
    assert called == ["nli"]


# ------------------------------------------------------------------------------------------------------------------ evidence_texts + make_check
def test_evidence_texts_orders_claim_wordings_before_quotes():
    c1 = mk_claim("c_1", "Claim one text.", quotes=("Quote of one.",))
    c2 = mk_claim("c_2", "Claim two text.", quotes=("Quote of two.",), near="Other wording of two.")
    texts = validators.evidence_texts(mk_job("partly", [c1, c2]))
    assert texts == ["Claim one text.", "Claim two text.", "Other wording of two.", "Quote of one.", "Quote of two.", "other quote"]
    assert validators.evidence_texts(mk_job("single", [c1, c2]), ["c_2"])[0] == "Claim two text."
    # a contradicting quote is never premise material
    c1.evidence.append(Evidence(source_id="s9", title="X", quote="contradicting quote", relation="contradicts"))
    assert "contradicting quote" not in validators.evidence_texts(mk_job("single", [c1]))


def test_make_check_runs_the_cheap_checks_before_the_models():
    nli, judge = FakeNli(ent=0.9), FakeJudge()
    chk = grounding.make_check(nli=nli, judge=judge)
    job = mk_job("single")
    # a rule failure never reaches the models
    assert chk("ViT-B/16 reaches 77.9% top-1 accuracy on ImageNet-1k.", ["c_1"], job)
    assert nli.calls == []
    assert chk("One study reports that ViT-B/16 reaches 79.9% top-1 accuracy on ImageNet-1k.", ["c_1"], job)
    assert nli.calls == []
    # a clean sentence goes to NLI
    assert chk("One study reports that ViT-B/16 attains 77.9% top-1 accuracy on ImageNet-1k.", ["c_1"], job) == []
    assert len(nli.calls) == 1
    # ... and the model verdict becomes a reason
    chk2 = grounding.make_check(nli=FakeNli(ent=0.0, con=0.9), judge=judge)
    r = chk2("One study reports that ViT-B/16 attains 77.9% top-1 accuracy on ImageNet-1k.", ["c_1"], job)
    assert r and "contradicts" in r[0]
    chk3 = grounding.make_check(nli=FakeNli(ent=0.0), judge=FakeJudge(False, 0.9, reason="adds a detail"))
    r = chk3("One study reports that ViT-B/16 attains 77.9% top-1 accuracy on ImageNet-1k.", ["c_1"], job)
    assert r and "not supported" in r[0]


# ---------------------------------------------------------------------------------------------------- natural style (template s5-v3)
def _natural(monkeypatch):
    monkeypatch.setenv("STAGE5_STYLE", "natural")


def test_natural_style_needs_a_description_of_the_source_only_for_single_claims(monkeypatch):
    from apps.api.agents.stage5_report import hedging
    _natural(monkeypatch)
    assert hedging.check_hedge("single", "A PET/CT segmentation study reports that federated learning matches centralized training.") == []
    assert hedging.check_hedge("single", "In a benchmark on chest X-rays, federated models lose three points.") == []
    assert hedging.check_hedge("single", "According to one study, differential privacy lowers accuracy.") == []
    assert hedging.check_hedge("single", "One study reports that it works.") == []
    assert hedging.check_hedge("single", "Federated learning matches centralized training.")                   # a bare claim is not enough for one source
    assert hedging.check_hedge("single", "A study clearly shows that federated learning wins.")                 # fact verbs stay forbidden
    assert hedging.check_hedge("partly", "Federated training matches centralized accuracy; a related result is degradation under skew.") == []
    assert hedging.check_hedge("partly", "Federated training clearly matches centralized accuracy.")
    assert hedging.check_hedge("supported", "Federated models reach accuracy comparable to centralized pooling.") == []
    assert hedging.check_hedge("supported", "Federated learning is proven to match centralized training.")


def test_natural_style_prompts_and_version_differ_from_the_attributed_style(monkeypatch):
    from apps.api.agents.stage5_report import prompts, settings
    _natural(monkeypatch)
    assert settings.template_version() == "s5-v3"
    msgs = prompts.summary_messages("summary", [{"n": 1, "text": "x", "tier": "single"}], 4, 6, {"question": "Q?", "parts": []})
    assert "labelled [supported], [partly] or [single]" in msgs[0]["content"] and "One study reports" not in msgs[0]["content"]
    monkeypatch.setenv("STAGE5_STYLE", "attributed")
    assert settings.template_version() == "s5-v2"
    assert "One study reports" in prompts.summary_messages("summary", [{"n": 1, "text": "x", "tier": "single"}], 4, 6, {"question": "Q?", "parts": []})[0]["content"]


def test_natural_style_summary_check_wants_a_described_source_for_single_findings(monkeypatch):
    from apps.api.agents.stage5_report import validators
    _natural(monkeypatch)
    body = [{"n": 1, "text": "A PET/CT study reports that federated learning matches centralized training.", "tier": "single"}]
    ok = validators.check_summary([{"text": "A PET/CT study reports that federated learning matches centralized training.", "from_sentences": [1]}], body, min_sentences=1, max_sentences=5)
    bad = validators.check_summary([{"text": "Federated learning matches centralized training.", "from_sentences": [1]}], body, min_sentences=1, max_sentences=5)
    assert ok == [] and any("what the source is" in r for r in bad)
