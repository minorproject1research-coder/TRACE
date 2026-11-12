"""Shared types of Stage 5 (the written report). Plain dataclasses, no I/O, no imports from the rest of the app, so every module of the
stage (loader, tiers, writer, validators, assembler) can use them and tests can build them by hand.

The idea of Stage 5: Python decides WHAT may be said (which claims, with which wording tier) and builds every citation; the LLM only phrases
one sentence per small cluster of claims and says which claim ids it used. A sentence that fails a Python check is retried once, then replaced by
a deterministic sentence or dropped. See docs/STAGE5.md."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

# Wording tiers of a claim (the Stage 4 label decides the tier; the tier decides the wording, never whether something is "true"):
TIER_SUPPORTED = "supported"        # two or more documents state it                     -> "Two sources report ..."
TIER_PARTLY = "partly"              # one document states it, another a close variant     -> "[A] reports X; [B] makes a related point"
TIER_SINGLE = "single"              # one document states it (Stage 4 "unverified")       -> "One study reports ..." (attributed, never as fact)
TIER_DISPUTED = "disputed"          # contradicted, or contested (support and a conflict)  -> only in the "Sources disagree" section
TIERS = (TIER_SUPPORTED, TIER_PARTLY, TIER_SINGLE, TIER_DISPUTED)

# Report status (the Stage 5 stage state stays within the usual pending/running/completed/failed; this is the status inside the report):
STATUS_COMPLETED = "completed"
STATUS_WARNINGS = "completed_with_warnings"     # some sentence fell back to the deterministic wording or was dropped
STATUS_INSUFFICIENT = "insufficient_evidence"   # nothing eligible to write about
STATUS_FAILED = "failed"
STATUSES = (STATUS_COMPLETED, STATUS_WARNINGS, STATUS_INSUFFICIENT, STATUS_FAILED)

ORIGIN_LLM = "llm"              # the LLM wrote it and every check passed
ORIGIN_FALLBACK = "fallback"    # deterministic sentence written by Python after the LLM sentence failed its checks twice
ORIGIN_TEMPLATE = "template"    # deterministic by design (limitations, disagreement pairs, references)


def make_claim_id(sub_question_id: str, claim_text: str) -> str:
    """A claim id that is the same on every rerun of Stage 4 (the database ids are not): hash of the sub-question id and the normalised claim text."""
    norm = re.sub(r"\s+", " ", (claim_text or "").strip().lower())
    return "c_" + hashlib.sha1(f"{sub_question_id}|{norm}".encode("utf-8")).hexdigest()[:10]


@dataclass
class Evidence:
    """One quote behind a claim (a Stage 4 evidence entry)."""
    source_id: str                          # retrieved_papers.id or web_sources.id
    title: str
    quote: str                              # verbatim from the source, already verified by Stage 3
    relation: str = "supports"              # supports | contradicts | near_match
    evidence_level: str = "abstract"        # full_text | abstract | web_snippet
    ref_key: str = ""                       # identity of the document (normalised title, same rule as Stage 4 doc_key); one reference per ref_key
    reliability: Optional[float] = None
    prob: Optional[float] = None
    via: Optional[str] = None               # "stage3_judge" when the Stage 3 judge already established the support
    near_claim: Optional[str] = None        # near_match only: the other document's own wording


@dataclass
class Claim:
    claim_id: str
    sub_question_id: str
    text: str                               # the claim as Stage 4 words it (representative wording)
    label: str                              # the Stage 4 label, never changed: supported | partially_supported | unverified | contradicted
    tier: Optional[str]                     # one of TIERS, or None when the claim is filtered out (see `filtered_reason`)
    contested: bool = False
    support_docs: int = 0
    contra_docs: int = 0
    confidence: float = 0.0
    evidence: list = field(default_factory=list)    # list[Evidence], supports first
    filtered_reason: Optional[str] = None   # why an otherwise labelled claim is not written about ("per_source_cap", "scope", "section_cap", ...)

    def supporting(self) -> list:
        return [e for e in self.evidence if e.relation == "supports"]

    def conflicting(self) -> list:
        return [e for e in self.evidence if e.relation == "contradicts"]


@dataclass
class Reference:
    """One entry of the reference list, built by Python from the database record; the LLM never writes any of these fields."""
    number: int                             # the [n] shown in the text, in order of first citation
    ref_key: str
    kind: str                               # paper | web
    title: str
    authors: list = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    source_ids: list = field(default_factory=list)  # all database ids that are this document
    evidence_level: Optional[str] = None    # the best level among its evidence entries: full_text | abstract | web_snippet
    published: Optional[str] = None         # free text, web sources
    domain: Optional[str] = None            # web sources: the site, taken from the url


@dataclass
class Disagreement:
    """Two sides that disagree (from a contradicted/contested claim or a row of the contradictions table). Written by Python from the quotes."""
    sub_question_id: str
    claim_a: str
    claim_b: str
    source_a_title: str = ""
    source_b_title: str = ""
    quote_a: str = ""
    quote_b: str = ""
    ref_key_a: str = ""
    ref_key_b: str = ""
    claim_id: Optional[str] = None          # the claim row it belongs to, when the link by text was found
    prob: Optional[float] = None
    reason: Optional[str] = None


@dataclass
class Job:
    """One sentence to write: 1 to 3 claims of the SAME tier from the same section. The LLM answers with one sentence and the ids it used."""
    job_id: str
    section_id: str
    tier: str                               # TIER_SUPPORTED | TIER_PARTLY | TIER_SINGLE
    claims: list = field(default_factory=list)      # list[Claim], at most 3


@dataclass
class Sentence:
    text: str
    claim_ids: list
    job_id: str
    tier: str
    origin: str = ORIGIN_LLM
    attempts: int = 1                       # LLM attempts used (0 for deterministic sentences)
    reasons: list = field(default_factory=list)     # the failed-check reasons of earlier attempts (kept for the audit)


@dataclass
class Section:
    section_id: str
    sub_question_id: str
    title: str                              # the sub-question text
    detail_questions: list = field(default_factory=list)
    sentences: list = field(default_factory=list)   # list[Sentence]
    disagreements: list = field(default_factory=list)       # list[Disagreement]
    gaps: list = field(default_factory=list)        # str: evidence not found / not sufficient for ... (from Stage 3 coverage)
    counts: dict = field(default_factory=dict)      # tier -> number of claims written, filtered, etc.
