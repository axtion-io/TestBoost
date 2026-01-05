"""Tests for test generation workflow operations."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import os


class TestTestGenerationMCPTools:
    """Tests for test generation MCP tools."""

    def test_test_generator_module_exists(self):
        """Test generator MCP module should be importable."""
        from src.mcp_servers import test_generator

        assert test_generator is not None

    def test_analyze_tool_exists(self):
        """Analyze tool should exist."""
        from src.mcp_servers.test_generator.tools import analyze

        assert analyze is not None

    def test_generate_unit_tool_exists(self):
        """Generate unit test tool should exist."""
        from src.mcp_servers.test_generator.tools import generate_unit

        assert generate_unit is not None

    def test_generate_integration_tool_exists(self):
        """Generate integration test tool should exist."""
        from src.mcp_servers.test_generator.tools import generate_integration

        assert generate_integration is not None

    def test_killer_tests_tool_exists(self):
        """Killer tests tool should exist."""
        from src.mcp_servers.test_generator.tools import killer_tests

        assert killer_tests is not None

    def test_mutation_tool_exists(self):
        """Mutation analysis tool should exist."""
        from src.mcp_servers.test_generator.tools import mutation

        assert mutation is not None


class TestTestGenerationFixtures:
    """Tests for LLM response fixtures."""

    @pytest.fixture
    def mock_llm_response(self):
        """Load mock LLM response from fixtures."""
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "fixtures", "llm_responses", "gemini_responses.json"
        )
        with open(fixture_path) as f:
            return json.load(f)

    def test_gemini_fixture_has_analyze_class(self, mock_llm_response):
        """Gemini fixture should have analyze_class response."""
        assert "analyze_class" in mock_llm_response
        assert "class_name" in mock_llm_response["analyze_class"]

    def test_gemini_fixture_has_generate_test(self, mock_llm_response):
        """Gemini fixture should have generate_test response."""
        assert "generate_test" in mock_llm_response
        assert "test_code" in mock_llm_response["generate_test"]


class TestTestGenerationLangChainTools:
    """Tests for LangChain tool integration."""

    def test_langchain_tools_module_exists(self):
        """LangChain tools module should be importable."""
        from src.mcp_servers.test_generator import langchain_tools

        assert langchain_tools is not None

    def test_llm_module_exists(self):
        """LLM module should be importable."""
        from src.lib import llm

        assert llm is not None

    def test_get_llm_function_exists(self):
        """get_llm function should exist."""
        from src.lib.llm import get_llm

        assert callable(get_llm)


class TestTestGenerationState:
    """Tests for test generation state model."""

    def test_session_type_enum_has_test_generation(self):
        """SessionType should have TEST_GENERATION value."""
        from src.db.models import SessionType

        assert hasattr(SessionType, "TEST_GENERATION") or "test_generation" in [s.value for s in SessionType]
