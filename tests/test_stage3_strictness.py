#!/usr/bin/env python3
"""
tests/test_stage3_strictness.py

Unit tests for Stage 3 strictness changes.
All tests use mocked LLM - no network calls.
Run with: pytest tests/test_stage3_strictness.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any
import numpy as np


# ============================================================
# TESTS: digest_generator tag parsing
# ============================================================

class TestDigestTagParsing:
    """Test _parse_answers_details in digest_generator.py"""

    def test_valid_objects_pass(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [
            {"detail": 1, "strength": "full"},
            {"detail": 2, "strength": "partial"},
        ]
        result = _parse_answers_details(raw, n_details=3)
        assert result == [
            {"detail": 1, "strength": "full"},
            {"detail": 2, "strength": "partial"},
        ]

    def test_legacy_int_list_becomes_partial(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [1, 2, 3]
        result = _parse_answers_details(raw, n_details=5)
        assert result == [
            {"detail": 1, "strength": "partial"},
            {"detail": 2, "strength": "partial"},
            {"detail": 3, "strength": "partial"},
        ]

    def test_invalid_strength_defaults_to_partial(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [{"detail": 1, "strength": "invalid"}]
        result = _parse_answers_details(raw, n_details=5)
        assert result == [{"detail": 1, "strength": "partial"}]

    def test_missing_strength_defaults_to_partial(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [{"detail": 1}]
        result = _parse_answers_details(raw, n_details=5)
        assert result == [{"detail": 1, "strength": "partial"}]

    def test_out_of_range_dropped(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [{"detail": 0, "strength": "full"}, {"detail": 6, "strength": "full"}]
        result = _parse_answers_details(raw, n_details=5)
        assert result == []

    def test_non_int_detail_dropped(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [{"detail": "1", "strength": "full"}, {"detail": 1.5, "strength": "full"}]
        result = _parse_answers_details(raw, n_details=5)
        assert result == []

    def test_non_list_becomes_empty(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        assert _parse_answers_details(None, 5) == []
        assert _parse_answers_details("not a list", 5) == []
        assert _parse_answers_details({"detail": 1}, 5) == []

    def test_dedupe_preserves_first(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [
            {"detail": 1, "strength": "full"},
            {"detail": 1, "strength": "partial"},
            {"detail": 2, "strength": "full"},
        ]
        result = _parse_answers_details(raw, n_details=5)
        assert result == [
            {"detail": 1, "strength": "full"},
            {"detail": 2, "strength": "full"},
        ]

    def test_malformed_items_dropped_not_crash(self):
        from apps.api.agents.stage3_summarizer.digest_generator import _parse_answers_details
        raw = [
            {"detail": 1, "strength": "full"},
            "not a dict",
            None,
            123,
            {"detail": 2, "strength": "partial"},
        ]
        result = _parse_answers_details(raw, n_details=5)
        assert result == [
            {"detail": 1, "strength": "full"},
            {"detail": 2, "strength": "partial"},
        ]


# ============================================================
# TESTS: detail_aspects splitting
# ============================================================

class TestAspectSplitting:
    """Test split_detail_aspects in detail_aspects.py"""

    @pytest.fixture
    def mock_squeezer_json(self):
        with patch("apps.api.agents.stage3_summarizer.detail_aspects.squeezer_json") as mock:
            yield mock

    def test_fallback_to_single_on_api_error(self, mock_squeezer_json):
        from apps.api.agents.stage3_summarizer.detail_aspects import split_detail_aspects
        mock_squeezer_json.side_effect = Exception("API error")
        result = split_detail_aspects("advantages and disadvantages", "sq_fallback_api", "topic")
        assert result == ["advantages and disadvantages"]

    def test_fallback_on_malformed_output(self, mock_squeezer_json):
        from apps.api.agents.stage3_summarizer.detail_aspects import split_detail_aspects
        mock_squeezer_json.return_value = {"aspects": "not a list"}
        result = split_detail_aspects("advantages and disadvantages", "sq_fallback_malformed", "topic")
        assert result == ["advantages and disadvantages"]

    def test_fallback_on_too_many_aspects(self, mock_squeezer_json):
        from apps.api.agents.stage3_summarizer.detail_aspects import split_detail_aspects
        mock_squeezer_json.return_value = {"aspects": ["a", "b", "c", "d"]}
        result = split_detail_aspects("advantages and disadvantages", "sq_fallback_many", "topic")
        assert result == ["advantages and disadvantages"]

    def test_fallback_on_empty_aspect(self, mock_squeezer_json):
        from apps.api.agents.stage3_summarizer.detail_aspects import split_detail_aspects
        mock_squeezer_json.return_value = {"aspects": ["valid", ""]}
        result = split_detail_aspects("advantages and disadvantages", "sq_fallback_empty", "topic")
        assert result == ["advantages and disadvantages"]

    def test_cache_hit_avoids_second_call(self, mock_squeezer_json):
        from apps.api.agents.stage3_summarizer.detail_aspects import (
            split_detail_aspects, _load_cache, ASPECT_CACHE_PATH
        )
        mock_squeezer_json.return_value = {"aspects": ["advantages of X", "disadvantages of X"]}
        
        # Use unique detail text to avoid cache from other tests
        test_detail = "advantages and disadvantages for cache test unique"
        test_id = "sq_cache_test_unique"
        
        # Delete cache file if it exists to ensure clean state
        if ASPECT_CACHE_PATH.exists():
            ASPECT_CACHE_PATH.unlink()
        
        # First call - should call LLM
        result1 = split_detail_aspects(test_detail, test_id, "topic")
        assert mock_squeezer_json.call_count == 1
        
        # Second call - should use cache
        result2 = split_detail_aspects(test_detail, test_id, "topic")
        assert mock_squeezer_json.call_count == 1  # No additional call
        assert result1 == result2

    def test_flatten_aspects_maps_correctly(self, mock_squeezer_json):
        from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects, _load_cache
        
        # Return different aspects for each detail to avoid near-duplicate merging
        call_count = [0]
        def mock_return(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"aspects": ["adv of X", "disadv of X"]}
            else:
                return {"aspects": ["examples of X", "benefits of X"]}
        mock_squeezer_json.side_effect = mock_return
        
        details = ["advantages and disadvantages", "examples and benefits"]
        aspects, mapping = flatten_aspects(details, "sq_flatten_test", "X")
        
        assert aspects == ["adv of X", "disadv of X", "examples of X", "benefits of X"]
        assert mapping == [0, 0, 1, 1]


# ============================================================
# TESTS: coverage_check with aspects
# ============================================================

class TestCoverageCheck:
    """Test coverage_check.py with aspects and tag strength"""

    def _make_mock_embedder(self):
        """Create a mock embedder that returns high similarity."""
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        return mock_embedder

    def test_one_full_tag_not_enough(self):
        """(a) One full tag is not enough (need MIN_COVER_FINDINGS=2)"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["advantages of X", "disadvantages of X"]
            aspect_to_detail = [0, 0]
            original_details = ["advantages and disadvantages of X"]
            
            digests = [{
                "source_id": "src1",
                "evidence_level": "full_text",
                "findings": [{
                    "claim": "X has many advantages",
                    "verified": True,
                    "answers_details": [{"detail": 1, "strength": "full"}],
                }],
            }]
            
            result = check_coverage(aspects, aspect_to_detail, original_details, digests)
            assert result["sufficient"] is False
            assert "advantages and disadvantages of X" in result["uncovered_details"]

    def test_two_full_tags_same_source_not_enough(self):
        """(b) Two full tags from same source not enough (need MIN_COVER_SOURCES=2)"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["advantages of X", "disadvantages of X"]
            aspect_to_detail = [0, 0]
            original_details = ["advantages and disadvantages of X"]
            
            digests = [{
                "source_id": "src1",
                "evidence_level": "full_text",
                "findings": [
                    {"claim": "X has many advantages", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                    {"claim": "X has some disadvantages", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]},
                ],
            }]
            
            result = check_coverage(aspects, aspect_to_detail, original_details, digests)
            assert result["sufficient"] is False
            assert "advantages and disadvantages of X" in result["uncovered_details"]

    def test_two_full_tags_two_sources_cover_aspect(self):
        """(c) Two full tags from two sources cover an aspect (need 2 findings per aspect from 2 sources)"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            # Both aspects need 2 full tags from 2 sources each
            aspects = ["advantages of X", "disadvantages of X"]
            aspect_to_detail = [0, 0]
            original_details = ["advantages and disadvantages of X"]
            
            digests = [
                {"source_id": "src1", "evidence_level": "full_text", "findings": [
                    {"claim": "X has many advantages", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                    {"claim": "X has some disadvantages", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]},
                ]},
                {"source_id": "src2", "evidence_level": "full_text", "findings": [
                    {"claim": "X has many advantages too", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                    {"claim": "X has some disadvantages too", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]},
                ]},
            ]
            
            # min_sources=2 to isolate aspect coverage from source-count rule
            result = check_coverage(aspects, aspect_to_detail, original_details, digests, min_sources=2)
            
            assert result["sufficient"] is True
            assert result["uncovered_details"] == []
            assert result["uncovered_aspects"] == []

    def test_two_sources_covered_but_insufficient_due_to_source_count(self):
        """Companion test: same fixture with min_sources=3 -> aspects covered but insufficient due to source count"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["advantages of X", "disadvantages of X"]
            aspect_to_detail = [0, 0]
            original_details = ["advantages and disadvantages of X"]
            
            digests = [
                {"source_id": "src1", "evidence_level": "full_text", "findings": [
                    {"claim": "X has many advantages", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                    {"claim": "X has some disadvantages", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]},
                ]},
                {"source_id": "src2", "evidence_level": "full_text", "findings": [
                    {"claim": "X has many advantages too", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                    {"claim": "X has some disadvantages too", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]},
                ]},
            ]
            
            # Default min_sources=3 -> 2 sources < 3, so insufficient despite full aspect coverage
            result = check_coverage(aspects, aspect_to_detail, original_details, digests)
            
            assert result["sufficient"] is False
            assert result["uncovered_details"] == []
            assert result["uncovered_aspects"] == []
            assert result["source_count"] == 2
            assert result["full_text_source_count"] == 2

    def test_partial_tags_never_cover(self):
        """(d) Partial tags never count toward coverage"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["advantages of X", "disadvantages of X"]
            aspect_to_detail = [0, 0]
            original_details = ["advantages and disadvantages of X"]
            
            digests = [
                {"source_id": "src1", "evidence_level": "full_text", "findings": [
                    {"claim": "X has advantages", "verified": True, "answers_details": [{"detail": 1, "strength": "partial"}]},
                ]},
                {"source_id": "src2", "evidence_level": "full_text", "findings": [
                    {"claim": "X has disadvantages", "verified": True, "answers_details": [{"detail": 2, "strength": "partial"}]},
                ]},
            ]
            
            result = check_coverage(aspects, aspect_to_detail, original_details, digests)
            assert result["sufficient"] is False
            assert "advantages and disadvantages of X" in result["uncovered_details"]

    def test_detail_with_two_aspects_uncovered_when_one_covered(self):
        """(e) Detail with two aspects uncovered when only one aspect covered"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["advantages of X", "disadvantages of X"]
            aspect_to_detail = [0, 0]
            original_details = ["advantages and disadvantages of X"]
            
            # Only aspect 1 (advantages) has 2 full tags from 2 sources
            # Aspect 2 (disadvantages) has 0 tags
            digests = [
                {"source_id": "src1", "evidence_level": "full_text", "findings": [
                    {"claim": "X has many advantages", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                ]},
                {"source_id": "src2", "evidence_level": "full_text", "findings": [
                    {"claim": "X has many advantages too", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]},
                ]},
            ]
            
            result = check_coverage(aspects, aspect_to_detail, original_details, digests)
            assert result["sufficient"] is False
            assert "advantages and disadvantages of X" in result["uncovered_details"]
            assert "disadvantages of X" in result["uncovered_aspects"]

    def test_legacy_digests_use_old_path(self):
        """(f) Legacy digests without tags still use old logic"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["advantages of X"]
            aspect_to_detail = [0]
            original_details = ["advantages of X"]
            
            # No answers_details key at all
            digests = [{
                "source_id": "src1",
                "evidence_level": "full_text",
                "findings": [{
                    "claim": "X has advantages",
                    "verified": True,
                    # No answers_details key
                }],
            }]
            
            result = check_coverage(aspects, aspect_to_detail, original_details, digests)
            # Falls back to similarity-based logic
            assert "uncovered_details" in result

    def test_weighted_source_count_unchanged(self):
        """(g) Weighted source count behavior is unchanged"""
        from apps.api.agents.stage3_summarizer.coverage_check import check_coverage, EVIDENCE_WEIGHT
        from unittest.mock import patch
        
        mock_embedder = MagicMock()
        def mock_encode(texts, normalize_embeddings=True):
            result = []
            for t in texts:
                vec = np.ones(384, dtype=np.float32) * 0.9
                vec = vec / (np.linalg.norm(vec) + 1e-8)
                result.append(vec)
            return np.array(result)
        mock_embedder = MagicMock()
        mock_embedder.encode = mock_encode
        
        with patch("apps.api.agents.stage3_summarizer.coverage_check.get_embedder", lambda: mock_embedder):
            aspects = ["a", "b"]
            aspect_to_detail = [0, 1]
            original_details = ["a", "b"]
            
            digests = [
                {"source_id": "s1", "evidence_level": "full_text", "findings": [{"claim": "c", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]}]},
                {"source_id": "s2", "evidence_level": "abstract", "findings": [{"claim": "c", "verified": True, "answers_details": [{"detail": 2, "strength": "full"}]}]},
                {"source_id": "s3", "evidence_level": "web_snippet", "findings": [{"claim": "c", "verified": True, "answers_details": [{"detail": 1, "strength": "full"}]}]},
            ]
            
            result = check_coverage(aspects, aspect_to_detail, original_details, digests, min_sources=3)
            # 1.0 + 0.5 + 0.5 = 2.0 < 3, so not sufficient
            assert result["sufficient"] is False
            assert result["source_count"] == 3
            assert result["full_text_source_count"] == 1


# ============================================================
# TESTS: audit_tag_precision AUC computation
# ============================================================

class TestAUCComputation:
    def test_auc_perfect_separation(self):
        from tests.audit_tag_precision import compute_auc
        auc = compute_auc([0.8, 0.9, 0.7], [0.3, 0.2, 0.4])
        assert auc == 1.0

    def test_auc_no_separation(self):
        from tests.audit_tag_precision import compute_auc
        auc = compute_auc([0.5, 0.5], [0.5, 0.5])
        assert auc == 0.5

    def test_auc_empty_lists(self):
        from tests.audit_tag_precision import compute_auc
        assert compute_auc([], [0.5]) == 0.0
        assert compute_auc([0.5], []) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])