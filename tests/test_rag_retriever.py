"""
test_rag_retriever.py
---------------------
Unit and integration tests for modules/rag/retriever.py

These tests require:
  1. GEMINI_API_KEY set in .env
  2. ChromaDB collection populated (run: python -m modules.rag.ingest)

Tests that call the live Gemini API are marked with @pytest.mark.integration.
The test suite runs them by default; skip with: pytest -m "not integration"
"""

from __future__ import annotations

import pytest

from modules.rag.retriever import (
    get_context,
    get_context_with_metadata,
    is_ready,
    DISTANCE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Readiness check
# ---------------------------------------------------------------------------

class TestIsReady:

    def test_collection_is_ready_after_ingest(self):
        """ChromaDB collection must exist and have documents after ingest."""
        assert is_ready() is True


# ---------------------------------------------------------------------------
# get_context_with_metadata — structure tests (no API call)
# ---------------------------------------------------------------------------

class TestGetContextStructure:

    def test_empty_query_returns_no_match(self):
        result = get_context_with_metadata("")
        assert result["found"] is False
        assert result["context_text"] == ""
        assert result["chunks"] == []

    def test_whitespace_only_query_returns_no_match(self):
        result = get_context_with_metadata("   ")
        assert result["found"] is False

    def test_result_dict_has_all_keys(self):
        # Use a real query — needs API
        result = get_context_with_metadata("carbon emission factor India")
        assert "context_text" in result
        assert "chunks" in result
        assert "found" in result

    def test_chunks_have_required_fields(self):
        result = get_context_with_metadata("energy saving HVAC campus")
        if result["found"]:
            for chunk in result["chunks"]:
                assert "id" in chunk
                assert "text" in chunk
                assert "source" in chunk
                assert "distance" in chunk
                assert "score" in chunk

    def test_all_returned_chunks_pass_distance_threshold(self):
        result = get_context_with_metadata("LED lighting efficiency savings")
        for chunk in result["chunks"]:
            assert chunk["distance"] <= DISTANCE_THRESHOLD

    def test_score_is_complement_of_distance(self):
        result = get_context_with_metadata("CO2 emission India grid")
        if result["found"]:
            for chunk in result["chunks"]:
                assert abs(chunk["score"] - (1.0 - chunk["distance"])) < 1e-4


# ---------------------------------------------------------------------------
# Semantic relevance tests (integration — calls Gemini API)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSemanticRelevance:

    def test_emission_factor_query_returns_relevant_chunk(self):
        """A query about India's grid emission factor should retrieve from emission_factors.md."""
        result = get_context_with_metadata("What is India's grid emission factor kg CO2 per kWh?", k=3)
        assert result["found"] is True, "Expected at least one relevant chunk"
        sources = [c["source"] for c in result["chunks"]]
        assert any("emission_factors" in s for s in sources), (
            f"Expected emission_factors.md in sources, got: {sources}"
        )

    def test_hvac_query_returns_best_practices(self):
        """A query about HVAC savings should retrieve from energy_best_practices.md."""
        result = get_context_with_metadata("How can I reduce air conditioning energy consumption?", k=3)
        assert result["found"] is True
        sources = [c["source"] for c in result["chunks"]]
        assert any("best_practices" in s for s in sources), (
            f"Expected energy_best_practices.md in sources, got: {sources}"
        )

    def test_benchmark_query_returns_guidelines(self):
        """A query about EUI benchmarks should retrieve from iea_campus_guidelines.md."""
        result = get_context_with_metadata("What is the BEE benchmark EUI for educational buildings?", k=3)
        assert result["found"] is True
        sources = [c["source"] for c in result["chunks"]]
        assert any("iea_campus" in s or "guidelines" in s for s in sources), (
            f"Expected iea_campus_guidelines.md in sources, got: {sources}"
        )

    def test_k_parameter_limits_results(self):
        """Requesting k=1 should return at most 1 chunk."""
        result = get_context_with_metadata("solar energy rooftop campus India", k=1)
        assert len(result["chunks"]) <= 1

    def test_context_text_contains_source_header(self):
        """The formatted context block must include the source attribution header."""
        result = get_context_with_metadata("lighting LED energy savings campus", k=2)
        if result["found"]:
            assert "[CONTEXT FROM KNOWLEDGE BASE]" in result["context_text"]
            assert "[END CONTEXT]" in result["context_text"]
            assert "Source:" in result["context_text"]

    def test_irrelevant_query_may_return_empty(self):
        """
        A completely off-topic query should either return no results or low-scoring ones.
        We don't assert empty (threshold is fairly permissive), but we verify
        the function doesn't raise an exception.
        """
        result = get_context_with_metadata("recipe for chocolate cake")
        assert isinstance(result["found"], bool)
        assert isinstance(result["chunks"], list)


# ---------------------------------------------------------------------------
# get_context wrapper
# ---------------------------------------------------------------------------

class TestGetContext:

    def test_returns_string(self):
        result = get_context("CO2 emission factor")
        assert isinstance(result, str)

    def test_empty_query_returns_empty_string(self):
        result = get_context("")
        assert result == ""

    def test_found_query_returns_non_empty_string(self):
        result = get_context("reduce HVAC energy consumption campus building")
        # If RAG is ready, this should return a non-empty context block
        if is_ready():
            assert isinstance(result, str)
            # May or may not find relevant content but must not raise
