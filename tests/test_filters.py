"""Tests for air_download.filters."""

import pytest

from air_download.filters import apply_inclusion_filter


@pytest.fixture
def sample_exams():
    """Return a list of sample exam dictionaries."""
    return [
        {"modality": "MR", "description": "BRAIN WITH AND WITHOUT CONTRAST"},
        {"modality": "CT", "description": "CT HEAD WITHOUT CONTRAST"},
        {"modality": "MR", "description": "SPINE CERVICAL WITHOUT CONTRAST"},
        {"modality": "XR", "description": "CHEST PA AND LATERAL"},
    ]


class TestApplyInclusionFilter:
    """Tests for apply_inclusion_filter."""

    def test_returns_all_when_patterns_is_none(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", None)
        assert result == sample_exams

    def test_returns_all_when_patterns_is_empty(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", "")
        assert result == sample_exams

    def test_single_pattern_match(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", "MR")
        assert len(result) == 2
        assert all(r["modality"] == "MR" for r in result)

    def test_multiple_patterns_or_logic(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", "MR,CT")
        assert len(result) == 3
        assert all(r["modality"] in ("MR", "CT") for r in result)

    def test_case_insensitive(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", "mr")
        assert len(result) == 2

    def test_partial_match_in_description(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "description", "BRAIN")
        assert len(result) == 1
        assert result[0]["description"] == "BRAIN WITH AND WITHOUT CONTRAST"

    def test_no_match_returns_empty(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", "US")
        assert result == []

    def test_missing_field_excluded(self):
        items = [
            {"modality": "MR", "description": "BRAIN"},
            {"description": "NO MODALITY HERE"},
        ]
        result = apply_inclusion_filter(items, "modality", "MR")
        assert len(result) == 1
        assert result[0]["modality"] == "MR"

    def test_whitespace_in_patterns_is_stripped(self, sample_exams):
        result = apply_inclusion_filter(sample_exams, "modality", " MR , CT ")
        assert len(result) == 3
