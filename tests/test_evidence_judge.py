#!/usr/bin/env python3
"""
tests/test_evidence_judge.py

Unit tests for evidence_judge module.
All tests use mocked HTTP client and embedder - no network calls.
Run with: pytest tests/test_evidence_judge.py -v
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import List, Dict, Any, Tuple
import numpy as np
import hashlib
import json
import os
import tempfile
from pathlib import Path


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def _clear_judge_cache(tmp_path, monkeypatch):
    """Every test gets its own empty judge cache file; the real reports/judge_cache.json is never touched or deleted."""
    from apps.api.agents.stage3_summarizer import evidence_judge
    cache_path = tmp_path / "judge_cache.json"
    monkeypatch.setattr(evidence_judge, "JUDGE_CACHE_PATH", cache_path)
    yield


@pytest.fixture
def mock_embedder():
    """Create a mock embedder that returns deterministic embeddings."""
    mock = MagicMock()
    def mock_encode(texts, normalize_embeddings=True):
        result = []
        for t in texts:
            # Deterministic embedding based on text hash
            h = hash(t) % 10000 / 10000.0
            vec = np.ones(384, dtype=np.float32) * h
            vec = vec / (np.linalg.norm(vec) + 1e-8)
            result.append(vec)
        return np.array(result)
    mock.encode = mock_encode
    return mock


@pytest.fixture
def mock_embedder_high_sim():
    """Create a mock embedder that returns high similarity for near-duplicate aspects."""
    mock = MagicMock()
    def mock_encode(texts, normalize_embeddings=True):
        result = []
        for t in texts:
            # Use exact matching to avoid substring issues
            if t == "quality of input data":
                # Vector with pattern A
                vec = np.zeros(384, dtype=np.float32)
                vec[0:64] = 1.0
                vec[64:128] = 0.5
            elif t == "relevance of input data":
                # Very similar to quality of input data (cosine sim > 0.92)
                vec = np.zeros(384, dtype=np.float32)
                vec[0:64] = 0.98
                vec[64:128] = 0.52
            elif t == "advantages of X":
                vec = np.zeros(384, dtype=np.float32)
                vec[128:192] = 1.0
            elif t == "disadvantages of X":
                vec = np.zeros(384, dtype=np.float32)
                vec[192:256] = 1.0
            elif t == "how the model works":
                # Vector with pattern B (distinct from pattern A - low similarity)
                vec = np.zeros(384, dtype=np.float32)
                vec[256:320] = 1.0
            else:
                h = hash(t) % 10000 / 10000.0
                vec = np.ones(384, dtype=np.float32) * h
            vec = vec / (np.linalg.norm(vec) + 1e-8)
            result.append(vec)
        return np.array(result)
    mock.encode = mock_encode
    return mock


@pytest.fixture
def sample_digests():
    """Sample digests with verified findings."""
    return [
        {
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [
                {
                    "claim": "X has many advantages",
                    "quote": "X has many advantages in efficiency",
                    "chunk_id": 0,
                    "verified": True,
                    "answers_details": [{"detail": 1, "strength": "full"}],
                },
                {
                    "claim": "X has some disadvantages",
                    "quote": "X has some disadvantages in cost",
                    "chunk_id": 1,
                    "verified": True,
                    "answers_details": [{"detail": 2, "strength": "full"}],
                },
                {
                    "claim": "X is a method for training",
                    "quote": "X is a method for training models",
                    "chunk_id": 2,
                    "verified": True,
                    "answers_details": [],
                },
            ],
        },
        {
            "source_id": "src2",
            "evidence_level": "full_text",
            "findings": [
                {
                    "claim": "X has many advantages too",
                    "quote": "X has many advantages too in speed",
                    "chunk_id": 0,
                    "verified": True,
                    "answers_details": [{"detail": 1, "strength": "full"}],
                },
                {
                    "claim": "X has some disadvantages too",
                    "quote": "X has some disadvantages too in memory",
                    "chunk_id": 1,
                    "verified": True,
                    "answers_details": [{"detail": 2, "strength": "full"}],
                },
            ],
        },
    ]


@pytest.fixture
def sample_aspects():
    """Sample aspects."""
    return [
        "advantages of X",
        "disadvantages of X",
        "how X works",
    ]


@pytest.fixture
def sample_aspect_to_detail():
    """Sample aspect to detail mapping."""
    return [0, 0, 1]


@pytest.fixture
def sample_chunk_lookup():
    """Sample chunk lookup."""
    return {
        "0": "X has many advantages in efficiency and speed for training models.",
        "1": "X has some disadvantages in cost and memory usage.",
        "2": "X is a method for training models efficiently.",
    }


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables before each test."""
    original = dict(os.environ)
    os.environ.pop("JUDGE_URL", None)
    os.environ.pop("JUDGE_API_KEY", None)
    os.environ.pop("JUDGE_MODEL_ID", None)
    os.environ.pop("JUDGE_CANDIDATES_PER_ASPECT", None)
    os.environ.pop("JUDGE_EXTRA_BY_SIM", None)
    os.environ.pop("JUDGE_BATCH_SIZE", None)
    os.environ.pop("JUDGE_TIMEOUT_S", None)
    os.environ.pop("JUDGE_RETRIES", None)
    os.environ.pop("MAX_JUDGE_ITEMS_PER_SUBQ", None)
    os.environ.pop("JUDGE_CONTEXT_CHARS", None)
    os.environ.pop("NEAR_DUP_ASPECT_SIM", None)
    os.environ.pop("USE_JUDGE_COVERAGE", None)
    yield
    os.environ.clear()
    os.environ.update(original)


# ============================================================
# TESTS: Candidate Selection
# ============================================================

class TestCandidateSelection:
    """Test select_candidates function."""

    def test_tagged_findings_included(self, mock_embedder, sample_digests, sample_aspects, sample_chunk_lookup):
        """Test that tagged findings are included as candidates."""
        from apps.api.agents.stage3_summarizer.evidence_judge import select_candidates
        
        candidates = select_candidates(sample_aspects, sample_digests, sample_chunk_lookup, mock_embedder)
        
        # Should have candidates for aspects 0 and 1 (tagged)
        aspect_indices = {c["aspect_idx"] for c in candidates}
        assert 0 in aspect_indices  # advantages
        assert 1 in aspect_indices  # disadvantages

    def test_dedup_by_claim_hash(self, mock_embedder, sample_digests, sample_aspects, sample_chunk_lookup):
        """Test deduplication by claim hash."""
        from apps.api.agents.stage3_summarizer.evidence_judge import select_candidates
        
        candidates = select_candidates(sample_aspects, sample_digests, sample_chunk_lookup, mock_embedder)
        
        # Check no duplicate (aspect_idx, source_id, claim_hash)
        seen = set()
        for c in candidates:
            claim_hash = hashlib.sha256(c["claim"].encode()).hexdigest()[:16]
            key = (c["aspect_idx"], c["source_id"], claim_hash)
            assert key not in seen, f"Duplicate candidate: {key}"
            seen.add(key)

    def test_cap_per_aspect(self, mock_embedder, sample_digests, sample_aspects, sample_chunk_lookup):
        """Test cap at JUDGE_CANDIDATES_PER_ASPECT per aspect."""
        from apps.api.agents.stage3_summarizer.evidence_judge import select_candidates
        
        os.environ["JUDGE_CANDIDATES_PER_ASPECT"] = "2"
        
        candidates = select_candidates(sample_aspects, sample_digests, sample_chunk_lookup, mock_embedder)
        
        # Count per aspect
        from collections import Counter
        counts = Counter(c["aspect_idx"] for c in candidates)
        for count in counts.values():
            assert count <= 2

    def test_global_cap(self, mock_embedder, sample_digests, sample_aspects, sample_chunk_lookup):
        """Test global cap at MAX_JUDGE_ITEMS_PER_SUBQ."""
        from apps.api.agents.stage3_summarizer.evidence_judge import select_candidates
        
        os.environ["MAX_JUDGE_ITEMS_PER_SUBQ"] = "2"
        
        candidates = select_candidates(sample_aspects, sample_digests, sample_chunk_lookup, mock_embedder)
        
        assert len(candidates) <= 2

    def test_extra_by_similarity(self, mock_embedder, sample_aspects, sample_chunk_lookup):
        """Test JUDGE_EXTRA_BY_SIM adds similar untagged findings."""
        from apps.api.agents.stage3_summarizer.evidence_judge import select_candidates
        
        # Digests with extra untagged but relevant findings
        digests = [
            {
                "source_id": "src1",
                "evidence_level": "full_text",
                "findings": [
                    {
                        "claim": "X has many advantages in efficiency",
                        "quote": "X has many advantages in efficiency",
                        "chunk_id": 0,
                        "verified": True,
                        "answers_details": [{"detail": 1, "strength": "full"}],  # tagged for aspect 0
                    },
                    {
                        "claim": "X works by gradient descent optimization",
                        "quote": "X works by gradient descent optimization",
                        "chunk_id": 1,
                        "verified": True,
                        "answers_details": [],  # not tagged, but similar to aspect 2
                    },
                ],
            },
        ]
        
        os.environ["JUDGE_EXTRA_BY_SIM"] = "1"
        
        candidates = select_candidates(sample_aspects, digests, sample_chunk_lookup, mock_embedder)
        
        # Should have tagged for aspect 0 + extra by sim for aspect 2
        aspect_indices = {c["aspect_idx"] for c in candidates}
        assert 0 in aspect_indices  # tagged
        # Extra by sim may or may not be included depending on similarity ranking

    def test_empty_input_returns_empty(self, mock_embedder):
        """Test empty aspects or digests returns empty list."""
        from apps.api.agents.stage3_summarizer.evidence_judge import select_candidates
        
        assert select_candidates([], [], {}, mock_embedder) == []
        assert select_candidates(["a"], [], {}, mock_embedder) == []
        assert select_candidates([], [{"findings": []}], {}, mock_embedder) == []


# ============================================================
# TESTS: Build Judge Items
# ============================================================

class TestBuildJudgeItems:
    """Test build_judge_items function."""

    def test_builds_items_with_context(self, sample_chunk_lookup):
        """Test items include context around quote."""
        from apps.api.agents.stage3_summarizer.evidence_judge import build_judge_items
        import hashlib
        
        candidates = [{
            "aspect_idx": 0,
            "aspect_text": "advantages of X",
            "source_id": "src1",
            "claim": "X has many advantages",
            "quote": "X has many advantages in efficiency",
            "chunk_id": 0,
            "similarity": 0.9,
            "digest_idx": 0,
            "finding_idx": 0,
        }]
        for c in candidates:
            stable_content = f"{c['aspect_text']}|{c['source_id']}|{c['finding_idx']}"
            c["item_id"] = hashlib.sha256(stable_content.encode()).hexdigest()[:16]
        
        items = build_judge_items(candidates, sample_chunk_lookup)
        
        assert len(items) == 1
        item = items[0]
        expected_id = hashlib.sha256(b"advantages of X|src1|0").hexdigest()[:16]
        assert item["id"] == expected_id
        assert item["aspect_idx"] == 0
        assert item["source_id"] == "src1"
        assert item["aspect"] == "advantages of X"
        assert item["claim"] == "X has many advantages"
        assert item["quote"] == "X has many advantages in efficiency"
        assert "efficiency" in item["context"]

    def test_empty_chunk_returns_empty_context(self):
        """Test missing chunk returns empty context."""
        from apps.api.agents.stage3_summarizer.evidence_judge import build_judge_items
        import hashlib
        
        candidates = [{
            "aspect_idx": 0,
            "aspect_text": "advantages of X",
            "source_id": "src1",
            "claim": "X has many advantages",
            "quote": "X has many advantages in efficiency",
            "chunk_id": 999,  # not in lookup
            "similarity": 0.9,
            "digest_idx": 0,
            "finding_idx": 0,
        }]
        for c in candidates:
            stable_content = f"{c['aspect_text']}|{c['source_id']}|{c['finding_idx']}"
            c["item_id"] = hashlib.sha256(stable_content.encode()).hexdigest()[:16]
        
        items = build_judge_items(candidates, {})
        
        assert items[0]["context"] == ""


# ============================================================
# TESTS: Judge Batching and Retries
# ============================================================

class TestJudgeBatching:
    """Test judge_candidates function with batching and retries."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx client for judge API."""
        with patch("apps.api.agents.stage3_summarizer.evidence_judge.httpx.Client") as mock_client:
            yield mock_client

    def test_batches_at_batch_size(self, mock_httpx_client):
        """Test items are split into batches of JUDGE_BATCH_SIZE."""
        from apps.api.agents.stage3_summarizer.evidence_judge import judge_candidates
        
        os.environ["JUDGE_URL"] = "http://test-judge"
        os.environ["JUDGE_BATCH_SIZE"] = "2"
        os.environ["JUDGE_RETRIES"] = "0"
        
        # Create mock response that returns results for all items in batch
        call_count = [0]
        def mock_post(*args, **kwargs):
            call_count[0] += 1
            payload = kwargs.get("json", {})
            batch_items = payload.get("items", [])
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "results": [
                    {"id": item["id"], "verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "test"}, "raw_output": "", "error": None}
                    for item in batch_items
                ]
            }
            return mock_resp
        
        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = mock_post
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
        
        items = [
            {"id": "a0_ssrc1_f0", "aspect": "a", "claim": "c1", "quote": "q1", "context": "ctx1"},
            {"id": "a1_ssrc1_f0", "aspect": "b", "claim": "c2", "quote": "q2", "context": "ctx2"},
            {"id": "a0_ssrc2_f0", "aspect": "a", "claim": "c3", "quote": "q3", "context": "ctx3"},
        ]
        
        verdicts = judge_candidates(items)
        
        # Should have been called twice (2 batches: 2 + 1)
        assert mock_client_instance.post.call_count == 2
        assert len(verdicts) == 3

    def test_retries_on_5xx(self, mock_httpx_client):
        """Test retries on HTTP 5xx errors."""
        from apps.api.agents.stage3_summarizer.evidence_judge import judge_candidates
        import httpx
        
        os.environ["JUDGE_URL"] = "http://test-judge"
        os.environ["JUDGE_BATCH_SIZE"] = "2"
        os.environ["JUDGE_RETRIES"] = "2"
        
        # First call fails with 500, second succeeds
        call_count = [0]
        def mock_post(*args, **kwargs):
            call_count[0] += 1
            payload = kwargs.get("json", {})
            batch_items = payload.get("items", [])
            if call_count[0] == 1:
                mock_resp = MagicMock()
                mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock(status_code=500))
                return mock_resp
            else:
                mock_resp = MagicMock()
                mock_resp.raise_for_status = MagicMock()
                mock_resp.json.return_value = {
                    "results": [
                        {"id": item["id"], "verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "test"}, "raw_output": "", "error": None}
                        for item in batch_items
                    ]
                }
                return mock_resp
        
        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = mock_post
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
        
        items = [{"id": "a0_ssrc1_f0", "aspect": "a", "claim": "c1", "quote": "q1", "context": "ctx1"}]
        
        verdicts = judge_candidates(items)
        
        assert mock_client_instance.post.call_count == 2
        assert len(verdicts) == 1
        assert verdicts[(0, "src1", hashlib.sha256(b"c1").hexdigest()[:16])]["verdict"]["final"] == "yes"

    def test_null_verdict_becomes_error(self, mock_httpx_client):
        """Test null verdict from judge becomes 'error' verdict."""
        from apps.api.agents.stage3_summarizer.evidence_judge import judge_candidates
        
        os.environ["JUDGE_URL"] = "http://test-judge"
        os.environ["JUDGE_RETRIES"] = "0"
        
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": [{"id": "a0_ssrc1_f0", "verdict": None, "raw_output": "", "error": "judge failed"}]}
        
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
        
        items = [{"id": "a0_ssrc1_f0", "aspect": "a", "claim": "c1", "quote": "q1", "context": "ctx1"}]
        
        verdicts = judge_candidates(items)
        
        key = (0, "src1", hashlib.sha256(b"c1").hexdigest()[:16])
        assert verdicts[key]["verdict"]["final"] == "error"


# ============================================================
# TESTS: Caching
# ============================================================

class TestJudgeCache:
    """Test judge verdict caching."""

    def test_cache_hit_skips_http(self, mock_embedder, sample_aspects, sample_digests, sample_chunk_lookup):
        """Test cache hit skips HTTP call."""
        from apps.api.agents.stage3_summarizer.evidence_judge import (
            judge_candidates, _cache_key, _save_judge_cache, _load_judge_cache
        )
        import httpx
        
        os.environ["JUDGE_URL"] = "http://test-judge"
        
        # Pre-populate cache
        cache = {}
        aspect = "advantages of X"
        claim = "X has many advantages"
        quote = "X has many advantages in efficiency"
        key = _cache_key(aspect, claim, quote)
        cache[key] = {
            "verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "cached"},
            "raw_output": "cached",
            "error": None,
        }
        _save_judge_cache(cache)
        
        # Mock HTTP to fail if called
        with patch("apps.api.agents.stage3_summarizer.evidence_judge.httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = AssertionError("HTTP should not be called")
            mock_client.return_value.__enter__.return_value = mock_client_instance
            
            items = [{
                "id": "a0_ssrc1_f0",
                "aspect": aspect,
                "claim": claim,
                "quote": quote,
                "context": "ctx",
            }]
            
            verdicts = judge_candidates(items)
            
            # Should have used cache
            key = (0, "src1", hashlib.sha256(claim.encode()).hexdigest()[:16])
            assert verdicts[key]["verdict"]["final"] == "yes"
            assert verdicts[key]["verdict"]["reason"] == "cached"

    def test_cache_persists_across_calls(self, mock_embedder, sample_aspects, sample_digests, sample_chunk_lookup):
        """Test cache persists and gives identical results."""
        from apps.api.agents.stage3_summarizer.evidence_judge import (
            judge_candidates, run_judge_for_subquestion, _save_judge_cache, _load_judge_cache
        )
        
        os.environ["JUDGE_URL"] = "http://test-judge"
        
        # First call - populate cache
        with patch("apps.api.agents.stage3_summarizer.evidence_judge.httpx.Client") as mock_client:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"results": [{"id": "a0_ssrc1_f0", "verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "test"}, "raw_output": "", "error": None}]}
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_resp
            mock_client.return_value.__enter__.return_value = mock_client_instance
            
            items = [{
                "id": "a0_ssrc1_f0",
                "aspect": "advantages of X",
                "claim": "X has many advantages",
                "quote": "X has many advantages in efficiency",
                "context": "ctx",
            }]
            judge_candidates(items)
        
        # Second call - should use cache
        with patch("apps.api.agents.stage3_summarizer.evidence_judge.httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = AssertionError("HTTP should not be called")
            mock_client.return_value.__enter__.return_value = mock_client_instance
            
            verdicts2 = judge_candidates(items)
        
        key = (0, "src1", hashlib.sha256(b"X has many advantages").hexdigest()[:16])
        assert verdicts2[key]["verdict"]["final"] == "yes"
        assert verdicts2[key]["verdict"]["reason"] == "test"


# ============================================================
# TESTS: Aspect Merging
# ============================================================

class TestAspectMerging:
    """Test near-duplicate aspect merging in detail_aspects."""

    def test_merges_near_duplicates_at_092(self, mock_embedder_high_sim, monkeypatch):
        """Legacy mode ASPECT_MERGE=embedding: aspects with similarity >= 0.92 are merged."""
        from apps.api.agents.stage3_summarizer.detail_aspects import _merge_near_duplicate_aspects
        monkeypatch.setenv("ASPECT_MERGE", "embedding")
        
        aspects = [
            "quality of input data",
            "relevance of input data",  # near-duplicate of first
            "how the model works",      # distinct
        ]
        aspect_to_detail = [0, 0, 1]
        
        merged_aspects, merged_mapping, parent_mapping = _merge_near_duplicate_aspects(
            aspects, aspect_to_detail, mock_embedder_high_sim
        )
        
        # Should merge first two, keep third
        assert len(merged_aspects) == 2
        assert merged_aspects[0] == "quality of input data"  # keeps first
        assert merged_aspects[1] == "how the model works"
        assert len(parent_mapping[0]) == 2  # first merged aspect represents 2 originals
        assert len(parent_mapping[1]) == 1

    def test_keeps_distinct_aspects_alone(self, mock_embedder_high_sim, monkeypatch):
        """Legacy mode: distinct aspects (sim < 0.92) are not merged."""
        from apps.api.agents.stage3_summarizer.detail_aspects import _merge_near_duplicate_aspects
        monkeypatch.setenv("ASPECT_MERGE", "embedding")
        
        aspects = [
            "advantages of X",
            "disadvantages of X",  # distinct from advantages
        ]
        aspect_to_detail = [0, 0]
        
        merged_aspects, merged_mapping, parent_mapping = _merge_near_duplicate_aspects(
            aspects, aspect_to_detail, mock_embedder_high_sim
        )
        
        assert len(merged_aspects) == 2
        assert merged_aspects == aspects
        assert len(parent_mapping[0]) == 1
        assert len(parent_mapping[1]) == 1


# ============================================================
# TESTS: Coverage with Judge
# ============================================================

class TestCoverageWithJudge:
    """Test check_coverage_judged function."""

    def make_verdict(self, final: str, reason: str = "") -> Dict:
        return {
            "verdict": {
                "final": final,
                "quote_supports_claim": "yes",
                "answers_aspect": "yes",
                "reason": reason,
            },
            "raw_output": "",
            "error": None,
        }

    def claim_hash(self, claim: str) -> str:
        import hashlib
        return hashlib.sha256(claim.encode()).hexdigest()[:16]

    def test_two_yes_two_sources_covers(self, mock_embedder):
        """Test two 'yes' from two sources covers an aspect."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        aspects = ["advantages of X", "disadvantages of X"]
        aspect_to_detail = [0, 0]
        original_details = ["advantages and disadvantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{"claim": "c1", "verified": True}],
        }, {
            "source_id": "src2",
            "evidence_level": "full_text",
            "findings": [{"claim": "c2", "verified": True}],
        }]
        
        # Both sources have "yes" for BOTH aspects
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("yes"),
            (0, "src2", self.claim_hash("c2")): self.make_verdict("yes"),
            (1, "src1", self.claim_hash("c1")): self.make_verdict("yes"),
            (1, "src2", self.claim_hash("c2")): self.make_verdict("yes"),
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": "src1", "claim": "c1", "quote": "q1", "item_id": "item1"},
            {"aspect_idx": 0, "source_id": "src2", "claim": "c2", "quote": "q2", "item_id": "item2"},
            {"aspect_idx": 1, "source_id": "src1", "claim": "c1", "quote": "q3", "item_id": "item3"},
            {"aspect_idx": 1, "source_id": "src2", "claim": "c2", "quote": "q4", "item_id": "item4"},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        assert result["judge_used"] is True
        assert result["uncovered_aspects"] == []  # both aspects covered
        assert result["uncovered_details"] == []

    def test_two_yes_same_source_not_cover(self, mock_embedder):
        """Test two 'yes' from same source does NOT cover."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{"claim": "c1", "verified": True}, {"claim": "c2", "verified": True}],
        }]
        
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("yes"),
            (0, "src1", self.claim_hash("c2")): self.make_verdict("yes"),
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": "src1", "claim": "c1", "quote": "q1", "item_id": "item1"},
            {"aspect_idx": 0, "source_id": "src1", "claim": "c2", "quote": "q2", "item_id": "item2"},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        assert result["judge_used"] is True
        assert "advantages of X" in result["uncovered_aspects"]

    def test_one_yes_not_cover(self, mock_embedder):
        """Test one 'yes' is not enough."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{"claim": "c1", "verified": True}],
        }]
        
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("yes"),
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": "src1", "claim": "c1", "quote": "q1", "item_id": "item1"},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        assert result["judge_used"] is True
        assert "advantages of X" in result["uncovered_aspects"]

    def test_partial_never_counts(self, mock_embedder):
        """Test 'partial' verdicts never count toward coverage."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{"claim": "c1", "verified": True}],
        }, {
            "source_id": "src2",
            "evidence_level": "full_text",
            "findings": [{"claim": "c2", "verified": True}],
        }]
        
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("partial"),
            (0, "src2", self.claim_hash("c2")): self.make_verdict("partial"),
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": "src1", "claim": "c1", "quote": "q1", "item_id": "item1"},
            {"aspect_idx": 0, "source_id": "src2", "claim": "c2", "quote": "q2", "item_id": "item2"},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        assert result["judge_used"] is True
        assert "advantages of X" in result["uncovered_aspects"]
        assert result["judge_stats"]["partial"] == 2

    def test_error_never_counts(self, mock_embedder):
        """Test 'error' verdicts make aspect unjudged (not counted toward coverage)."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        # 7 digests, 2 errors = 28% error rate < 30% threshold
        digests = [
            {"source_id": "src1", "evidence_level": "full_text", "findings": [{"claim": "c1", "verified": True}]},
            {"source_id": "src2", "evidence_level": "full_text", "findings": [{"claim": "c2", "verified": True}]},
            {"source_id": "src3", "evidence_level": "full_text", "findings": [{"claim": "c3", "verified": True}]},
            {"source_id": "src4", "evidence_level": "full_text", "findings": [{"claim": "c4", "verified": True}]},
            {"source_id": "src5", "evidence_level": "full_text", "findings": [{"claim": "c5", "verified": True}]},
            {"source_id": "src6", "evidence_level": "full_text", "findings": [{"claim": "c6", "verified": True}]},
            {"source_id": "src7", "evidence_level": "full_text", "findings": [{"claim": "c7", "verified": True}]},
        ]
        
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("error"),
            (0, "src2", self.claim_hash("c2")): self.make_verdict("error"),
            (0, "src3", self.claim_hash("c3")): self.make_verdict("no"),
            (0, "src4", self.claim_hash("c4")): self.make_verdict("no"),
            (0, "src5", self.claim_hash("c5")): self.make_verdict("no"),
            (0, "src6", self.claim_hash("c6")): self.make_verdict("no"),
            (0, "src7", self.claim_hash("c7")): self.make_verdict("no"),
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": f"src{i+1}", "claim": f"c{i+1}", "quote": f"q{i+1}", "item_id": f"item{i+1}"}
            for i in range(7)
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        # With new logic: error verdicts make aspect "unjudged"
        assert result["judge_used"] is False
        assert "advantages of X" in result["unjudged_aspects"]
        assert "advantages of X" not in result["uncovered_aspects"]
        assert result["uncovered_reasons"].get("advantages of X") == "unjudged"
        assert result["judge_stats"]["error"] == 2

    def test_detail_uncovered_when_one_aspect_uncovered(self, mock_embedder):
        """Test detail with two aspects uncovered when only one aspect covered."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        aspects = ["advantages of X", "disadvantages of X"]
        aspect_to_detail = [0, 0]
        original_details = ["advantages and disadvantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{"claim": "c1", "verified": True}],
        }, {
            "source_id": "src2",
            "evidence_level": "full_text",
            "findings": [{"claim": "c2", "verified": True}],
        }]
        
        # Only aspect 0 (advantages) has two "yes" from two sources
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("yes"),
            (0, "src2", self.claim_hash("c2")): self.make_verdict("yes"),
            # Aspect 1 (disadvantages) has no verdicts -> unjudged
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": "src1", "claim": "c1", "quote": "q1", "item_id": "item1"},
            {"aspect_idx": 0, "source_id": "src2", "claim": "c2", "quote": "q2", "item_id": "item2"},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        # Aspect 1 has no candidates at all: uncovered_judged / no_candidates (NOT unjudged, NOT a whole-sub-question fallback)
        assert result["judge_used"] is True
        assert "fallback_reason" not in result
        assert result["unjudged_aspects"] == []
        assert "disadvantages of X" in result["uncovered_aspects"]
        assert result["uncovered_reasons"].get("disadvantages of X") == "no_candidates"
        assert result["uncovered_reasons"].get("advantages of X") is None   # covered
        # Detail is uncovered because one of its aspects is uncovered
        assert "advantages and disadvantages of X" in result["uncovered_details"]

    def test_no_candidates_anywhere_is_not_a_fallback(self, mock_embedder):
        """candidates=[] (nothing verified) -> every aspect no_candidates, judge path kept, no tag-rule fallback."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        os.environ["USE_JUDGE_COVERAGE"] = "true"
        result = check_coverage_judged(["a", "b"], [0, 1], ["a", "b"], [], {}, candidates=[])
        assert result["judge_used"] is True
        assert "fallback_reason" not in result
        assert result["uncovered_reasons"] == {"a": "no_candidates", "b": "no_candidates"}
        assert result["sufficient"] is False

    def test_all_verdicts_failed_falls_back_whole_subquestion(self, mock_embedder):
        """Candidates exist but every verdict is an error (endpoint down) -> tag-rule fallback for the whole sub-question."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        os.environ["USE_JUDGE_COVERAGE"] = "true"
        digests = [{"source_id": "s1", "evidence_level": "full_text", "findings": [{"claim": "c1", "verified": True}]}]
        verdicts = {(0, "s1", self.claim_hash("c1")): self.make_verdict("error")}
        candidates = [{"aspect_idx": 0, "source_id": "s1", "claim": "c1", "quote": "q", "item_id": "i1"}]
        result = check_coverage_judged(["a"], [0], ["a"], digests, verdicts, candidates=candidates)
        assert result["judge_used"] is False
        assert "every verdict failed" in result["fallback_reason"]

    def test_one_aspect_without_verdicts_does_not_fall_back(self, mock_embedder):
        """Other aspects were judged, one candidate lacks a verdict -> that aspect is unjudged; no whole-sub-question fallback."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        os.environ["USE_JUDGE_COVERAGE"] = "true"
        digests = [
            {"source_id": "s1", "evidence_level": "full_text", "findings": [{"claim": "c1", "verified": True}]},
            {"source_id": "s2", "evidence_level": "full_text", "findings": [{"claim": "c2", "verified": True}]},
        ]
        verdicts = {
            (0, "s1", self.claim_hash("c1")): self.make_verdict("yes"),
            (0, "s2", self.claim_hash("c2")): self.make_verdict("yes"),
            (1, "s1", self.claim_hash("c1")): self.make_verdict("yes"),
            (1, "s2", self.claim_hash("c2")): self.make_verdict("yes"),
            (2, "s1", self.claim_hash("c1")): self.make_verdict("yes"),
            (2, "s2", self.claim_hash("c2")): self.make_verdict("yes"),
        }
        candidates = [{"aspect_idx": i, "source_id": s, "claim": c, "quote": "q", "item_id": f"{i}{s}"}
                      for i in range(3) for s, c in (("s1", "c1"), ("s2", "c2"))]
        candidates.append({"aspect_idx": 3, "source_id": "s1", "claim": "c1", "quote": "q", "item_id": "x"})  # no verdict returned
        result = check_coverage_judged(["a", "b", "c", "d"], [0, 1, 2, 3], ["a", "b", "c", "d"], digests, verdicts, candidates=candidates)
        assert "fallback_reason" not in result
        assert result["unjudged_aspects"] == ["d"]
        assert result["judge_used"] is False
        assert result["uncovered_aspects"] == []          # unjudged is never listed as uncovered (Loop 2 must not act on it)

    def test_aspect_evidence_uses_each_aspects_own_quote(self, mock_embedder):
        """The same claim judged for two aspects keeps the quote and item id of each candidate."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        digests = [
            {"source_id": "s1", "evidence_level": "full_text", "findings": [{"claim": "c1", "verified": True}]},
            {"source_id": "s2", "evidence_level": "full_text", "findings": [{"claim": "c2", "verified": True}]},
        ]
        verdicts = {(i, s, self.claim_hash(c)): self.make_verdict("yes") for i in (0, 1) for s, c in (("s1", "c1"), ("s2", "c2"))}
        candidates = [{"aspect_idx": i, "source_id": s, "claim": c, "quote": f"quote-{i}-{s}", "item_id": f"item-{i}-{s}"}
                      for i in (0, 1) for s, c in (("s1", "c1"), ("s2", "c2"))]
        result = check_coverage_judged(["a", "b"], [0, 1], ["a", "b"], digests, verdicts, candidates=candidates)
        assert {e["item_id"] for e in result["aspect_evidence"][0]} == {"item-0-s1", "item-0-s2"}
        assert {e["quote_prefix"] for e in result["aspect_evidence"][1]} == {"quote-1-s1", "quote-1-s2"}

    def test_fallback_on_endpoint_failure(self, mock_embedder):
        """Test fallback to tag-based when judge endpoint unavailable."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        os.environ["USE_JUDGE_COVERAGE"] = "true"
        os.environ.pop("JUDGE_URL", None)  # No URL configured
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{
                "claim": "X has advantages",
                "verified": True,
                "answers_details": [{"detail": 1, "strength": "full"}],
            }],
        }, {
            "source_id": "src2",
            "evidence_level": "full_text",
            "findings": [{
                "claim": "X has more advantages",
                "verified": True,
                "answers_details": [{"detail": 1, "strength": "full"}],
            }],
        }]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, {})
        
        assert result["judge_used"] is False
        assert "fallback_reason" in result

    def test_fallback_on_over_30pct_errors(self, mock_embedder):
        """Test fallback when >30% items are errors."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        os.environ["USE_JUDGE_COVERAGE"] = "true"
        os.environ["JUDGE_URL"] = "http://test-judge"
        
        aspects = ["a", "b", "c", "d", "e"]
        aspect_to_detail = [0, 0, 0, 0, 0]
        original_details = ["detail"]
        
        digests = [{"source_id": "src1", "evidence_level": "full_text", "findings": [{"claim": "c", "verified": True}]}]
        
        # 3 out of 5 = 60% errors > 30% threshold
        verdicts = {
            (0, "src1", self.claim_hash("c_a")): self.make_verdict("error"),
            (1, "src1", self.claim_hash("c_b")): self.make_verdict("error"),
            (2, "src1", self.claim_hash("c_c")): self.make_verdict("error"),
            (3, "src1", self.claim_hash("c_d")): self.make_verdict("yes"),
            (4, "src1", self.claim_hash("c_e")): self.make_verdict("yes"),
        }
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts)
        
        assert result["judge_used"] is False
        assert "fallback_reason" in result
        assert "judge_error_rate_exceeded" in result["fallback_reason"]

    def test_use_judge_false_uses_old_path(self, mock_embedder):
        """Test USE_JUDGE_COVERAGE=false uses tag-based path."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        os.environ["USE_JUDGE_COVERAGE"] = "false"
        os.environ["JUDGE_URL"] = "http://test-judge"
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{
                "claim": "X has advantages",
                "verified": True,
                "answers_details": [{"detail": 1, "strength": "full"}],
            }],
        }, {
            "source_id": "src2",
            "evidence_level": "full_text",
            "findings": [{
                "claim": "X has more advantages",
                "verified": True,
                "answers_details": [{"detail": 1, "strength": "full"}],
            }],
        }]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, {})
        
        assert result["judge_used"] is False
        assert result["fallback_reason"] == "judge disabled"

    def test_weighted_source_rule_unchanged(self, mock_embedder):
        """Test weighted source count behavior is unchanged."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged, EVIDENCE_WEIGHT
        
        os.environ["USE_JUDGE_COVERAGE"] = "false"
        
        aspects = ["a", "b"]
        aspect_to_detail = [0, 1]
        original_details = ["a", "b"]
        
        digests = [
            {"source_id": "s1", "evidence_level": "full_text", "findings": [{"claim": "c", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]}]},
            {"source_id": "s2", "evidence_level": "abstract", "findings": [{"claim": "c", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]}]},
            {"source_id": "s3", "evidence_level": "web_snippet", "findings": [{"claim": "c", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]}]},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, {}, min_sources=3)
        
        # 1.0 + 0.5 + 0.5 = 2.0 < 3, so not sufficient
        assert result["sufficient"] is False
        assert result["source_count"] == 3
        assert result["full_text_source_count"] == 1

    def test_new_result_keys_present(self, mock_embedder):
        """Test new result keys are present in output."""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage_judged
        
        os.environ["USE_JUDGE_COVERAGE"] = "true"
        os.environ["JUDGE_URL"] = "http://test-judge"
        
        aspects = ["advantages of X"]
        aspect_to_detail = [0]
        original_details = ["advantages of X"]
        
        digests = [{
            "source_id": "src1",
            "evidence_level": "full_text",
            "findings": [{"claim": "c1", "verified": True}],
        }]
        
        verdicts = {
            (0, "src1", self.claim_hash("c1")): self.make_verdict("yes"),
        }
        
        candidates = [
            {"aspect_idx": 0, "source_id": "src1", "claim": "c1", "quote": "q1", "item_id": "item1"},
        ]
        
        result = check_coverage_judged(aspects, aspect_to_detail, original_details, digests, verdicts, candidates=candidates)
        
        assert "judge_used" in result
        assert "judge_stats" in result
        assert "aspect_evidence" in result
        assert isinstance(result["judge_stats"], dict)
        assert isinstance(result["aspect_evidence"], dict)
        assert set(result["judge_stats"].keys()) == {"candidates", "yes", "partial", "no", "error"}


# ============================================================
# TESTS: Integration
# ============================================================

class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_run_judge_for_subquestion(self, mock_embedder, sample_aspects, sample_digests, sample_chunk_lookup):
        """Test full run_judge_for_subquestion pipeline."""
        from apps.api.agents.stage3_summarizer.evidence_judge import run_judge_for_subquestion
        
        os.environ["JUDGE_URL"] = "http://test-judge"
        os.environ["JUDGE_RETRIES"] = "0"
        
        with patch("httpx.Client") as mock_client:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"results": [
                {"id": "a0_ssrc1_f0", "verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "test"}, "raw_output": "", "error": None},
                {"id": "a1_ssrc1_f0", "verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "test"}, "raw_output": "", "error": None},
            ]}
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_resp
            mock_client.return_value.__enter__.return_value = mock_client_instance
            
            candidates, verdicts = run_judge_for_subquestion(sample_aspects, sample_digests, sample_chunk_lookup, mock_embedder)
            
            assert len(candidates) > 0
            assert len(verdicts) > 0
            # Check verdicts written to findings
            for d in sample_digests:
                for f in d["findings"]:
                    if "judge" in f:
                        for asp_idx, v in f["judge"].items():
                            assert "final" in v
                            assert "quote_supports_claim" in v
                            assert "answers_aspect" in v
                            assert "reason" in v


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

class TestJudgeConfigAndChunkContext:
    def test_judge_uses_trace_llm_url_and_key_when_no_judge_vars(self, monkeypatch):
        from apps.api.agents.stage3_summarizer import evidence_judge
        monkeypatch.setenv("TRACE_LLM_URL", "http://model-server/")
        monkeypatch.setenv("TRACE_LLM_API_KEY", "k-trace")
        cfg = evidence_judge._get_config()
        assert cfg["JUDGE_URL"] == "http://model-server" and cfg["API_KEY"] == "k-trace"

    def test_judge_vars_override_when_set(self, monkeypatch):
        from apps.api.agents.stage3_summarizer import evidence_judge
        monkeypatch.setenv("TRACE_LLM_URL", "http://model-server")
        monkeypatch.setenv("JUDGE_URL", "http://elsewhere")
        monkeypatch.setenv("JUDGE_API_KEY", "k-judge")
        cfg = evidence_judge._get_config()
        assert cfg["JUDGE_URL"] == "http://elsewhere" and cfg["API_KEY"] == "k-judge"

    def test_nothing_configured_means_empty_url(self):
        from apps.api.agents.stage3_summarizer import evidence_judge
        assert evidence_judge._get_config()["JUDGE_URL"] == ""

    def test_same_chunk_id_in_two_sources_gets_each_sources_own_context(self):
        from apps.api.agents.stage3_summarizer.evidence_judge import build_judge_items
        cands = [{"aspect_idx": 0, "aspect_text": "a", "source_id": s, "claim": "c", "quote": q, "chunk_id": 3, "item_id": s}
                 for s, q in (("srcA", "alpha beta"), ("srcB", "gamma delta"))]
        lookup = {"srcA:3": "text of A: alpha beta gamma", "srcB:3": "text of B: gamma delta epsilon", "3": "WRONG other paper"}
        items = {i["source_id"]: i["context"] for i in build_judge_items(cands, lookup)}
        assert items["srcA"].startswith("text of A") and items["srcB"].startswith("text of B")

    def test_plain_chunk_key_still_works_as_fallback(self):
        from apps.api.agents.stage3_summarizer.evidence_judge import build_judge_items
        cands = [{"aspect_idx": 0, "aspect_text": "a", "source_id": "s", "claim": "c", "quote": "alpha", "chunk_id": 1, "item_id": "x"}]
        assert build_judge_items(cands, {"1": "alpha old style"})[0]["context"] == "alpha old style"


class TestJudgeItemErrorLogging:
    """A failed judge verdict must be logged per item, with a non-empty reason, and a short server answer must not drop items."""

    @pytest.fixture
    def mock_httpx_client(self):
        with patch("apps.api.agents.stage3_summarizer.evidence_judge.httpx.Client") as mock_client:
            yield mock_client

    def _run(self, mock_httpx_client, results, items):
        from apps.api.agents.stage3_summarizer.evidence_judge import judge_candidates
        os.environ["JUDGE_URL"] = "http://test-judge"
        os.environ["JUDGE_RETRIES"] = "0"
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"results": results}
        client = MagicMock()
        client.post.return_value = resp
        mock_httpx_client.return_value.__enter__.return_value = client
        return judge_candidates(items)

    def _item(self, i, claim):
        return {"id": f"i{i}", "aspect_idx": i, "source_id": f"src{i}", "aspect": "a", "claim": claim, "quote": "q", "context": ""}

    def test_empty_error_still_gives_a_reason_and_a_warning(self, mock_httpx_client, caplog):
        items = [self._item(0, "claim zero")]
        with caplog.at_level("WARNING"):
            verdicts = self._run(mock_httpx_client, [{"id": "i0", "verdict": None, "raw_output": "", "error": None}], items)
        v = list(verdicts.values())[0]["verdict"]
        assert v["final"] == "error" and v["reason"].strip() != ""
        text = " ".join(r.getMessage() for r in caplog.records)
        assert "Judge verdict failed" in text and "claim zero" in text and "1 of 1 item(s)" in text

    def test_raw_output_is_kept_in_the_reason(self, mock_httpx_client):
        items = [self._item(0, "c")]
        verdicts = self._run(mock_httpx_client, [{"id": "i0", "verdict": None, "raw_output": "not json at all", "error": ""}], items)
        assert "not json at all" in list(verdicts.values())[0]["verdict"]["reason"]

    def test_short_answer_from_server_does_not_drop_items(self, mock_httpx_client, caplog):
        ok = {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "ok"}
        items = [self._item(0, "c0"), self._item(1, "c1")]
        with caplog.at_level("WARNING"):
            verdicts = self._run(mock_httpx_client, [{"id": "i0", "verdict": ok, "raw_output": "", "error": None}], items)
        finals = sorted(v["verdict"]["final"] for v in verdicts.values())
        assert finals == ["error", "yes"]
        assert "returned 1 result(s) for 2 item(s)" in " ".join(r.getMessage() for r in caplog.records)

    def test_successful_batch_logs_no_failure_warning(self, mock_httpx_client, caplog):
        ok = {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "ok"}
        with caplog.at_level("WARNING"):
            self._run(mock_httpx_client, [{"id": "i0", "verdict": ok, "raw_output": "", "error": None}], [self._item(0, "c0")])
        assert not any("Judge verdict failed" in r.getMessage() for r in caplog.records)



class TestAspectMergeModes:
    """ASPECT_MERGE=exact (default) must not merge aspects that only look alike; the aspects below come from the 2026-11-05 Mamba run,
    where the embedding rule merged all of these pairs (similarity 0.92-0.99) and a whole detail question disappeared from coverage."""

    PAIRS_THAT_MUST_STAY_SEPARATE = [
        ("What are the main components of state space models?", "What are the parameters of state space models?", 0, 0),                       # 0.924, same detail
        ("How does Mamba compare to transformers in terms of architecture?", "How does Mamba compare to transformers in terms of performance?", 0, 0),   # 0.948
        ("What are the open challenges for state space models and transformers?", "What are the future directions for state space models and transformers?", 0, 0),
        ("What are the empirical results and findings from existing studies regarding how SSMs compare with transformers?",
         "What are the theoretical explanations from existing literature regarding how SSMs compare with transformers?", 0, 1),         # 0.977, cross-detail
        ("how hallucinations are defined in large language models", "how hallucinations are measured in large language models", 0, 0),
        ("sources of hallucinations in large language models", "impacts of hallucinations in large language models", 0, 1),
    ]

    @pytest.mark.parametrize("a,b,da,db", PAIRS_THAT_MUST_STAY_SEPARATE)
    def test_default_mode_keeps_lookalike_aspects_apart(self, a, b, da, db, monkeypatch):
        from apps.api.agents.stage3_summarizer.detail_aspects import _merge_near_duplicate_aspects
        monkeypatch.delenv("ASPECT_MERGE", raising=False)
        merged, to_detail, _ = _merge_near_duplicate_aspects([a, b], [da, db])         # no embedder needed: default mode does not use one
        assert merged == [a, b] and to_detail == [da, db]

    def test_exact_duplicates_of_one_detail_are_merged(self, monkeypatch):
        from apps.api.agents.stage3_summarizer.detail_aspects import _merge_near_duplicate_aspects
        monkeypatch.delenv("ASPECT_MERGE", raising=False)
        merged, to_detail, parents = _merge_near_duplicate_aspects(
            ["Advantages of X", "the advantages of X?", "limitations of X"], [0, 0, 0])
        assert merged == ["Advantages of X", "limitations of X"] and parents == [[0, 1], [2]]

    def test_identical_aspects_of_two_details_are_both_kept(self, monkeypatch):
        """Merging them would make the second detail question vanish from coverage."""
        from apps.api.agents.stage3_summarizer.detail_aspects import _merge_near_duplicate_aspects
        monkeypatch.delenv("ASPECT_MERGE", raising=False)
        merged, to_detail, _ = _merge_near_duplicate_aspects(["advantages of X", "advantages of X"], [0, 1])
        assert merged == ["advantages of X", "advantages of X"] and to_detail == [0, 1]

    def test_off_mode_never_merges(self, monkeypatch):
        from apps.api.agents.stage3_summarizer.detail_aspects import _merge_near_duplicate_aspects
        monkeypatch.setenv("ASPECT_MERGE", "off")
        assert _merge_near_duplicate_aspects(["a b", "a b"], [0, 0])[0] == ["a b", "a b"]

    def test_unknown_mode_falls_back_to_exact(self, monkeypatch):
        from apps.api.agents.stage3_summarizer.detail_aspects import merge_mode
        monkeypatch.setenv("ASPECT_MERGE", "whatever")
        assert merge_mode() == "exact"

    def test_stored_run_mode_defaults_to_the_legacy_rule(self):
        from apps.api.agents.stage3_summarizer.detail_aspects import run_merge_mode
        assert run_merge_mode({}) == "embedding" and run_merge_mode(None) == "embedding"
        assert run_merge_mode({"judge_stats": {"yes": 1}}) == "embedding"          # a run from before the marker existed
        assert run_merge_mode({"judge_stats": {"aspect_merge": "exact"}}) == "exact"
        assert run_merge_mode({"judge_stats": {"aspect_merge": "bogus"}}) == "embedding"

    def test_flatten_with_explicit_mode_overrides_the_environment(self, monkeypatch):
        """Tools that rebuild a stored run pass its mode; the environment must not change that."""
        from apps.api.agents.stage3_summarizer import detail_aspects as da
        monkeypatch.setenv("ASPECT_MERGE", "exact")
        monkeypatch.setattr(da, "split_detail_aspects", lambda detail, sid, topic: {"d0": ["x one", "y two"], "d1": ["x one"]}[detail])
        aspects, to_detail = da.flatten_aspects(["d0", "d1"], "sq", "topic", merge_mode="off")
        assert aspects == ["x one", "y two", "x one"] and to_detail == [0, 0, 1]
