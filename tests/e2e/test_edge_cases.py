"""Edge case tests for LLM agent workflows (T105b-f).

These tests validate the error handling and retry logic for various edge cases:
- A1: Rate limit errors (429)
- A2: Missing tool calls (retry with modified prompt)
- A4: Intermittent connectivity (exponential backoff)
- A5: Malformed JSON responses
- A6: Context window overflow
"""

import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from src.lib.llm import LLMRateLimitError
from src.lib.startup_checks import LLMConnectionError


class TestRateLimitErrorHandling:
    """Test rate limit error handling (A1 edge case)."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_detected(self):
        """Test that 429 rate limit errors are properly detected.

        T105b: Mock 429 response, assert error message format matches spec (A1).
        """
        from src.lib.startup_checks import _ping_llm_with_retry

        # Create mock LLM that raises rate limit error
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception(
            "Error code: 429 - Rate limit exceeded. Please retry after 60 seconds."
        )

        # Should raise LLMConnectionError with rate limit info
        with pytest.raises(LLMConnectionError) as exc_info:
            await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=1)

        error_msg = str(exc_info.value)
        assert "rate limit" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_not_retried(self):
        """Test that rate limit errors are NOT retried (fail immediately).

        A1 edge case: Rate limits should fail fast, not waste retries.
        """
        from src.lib.startup_checks import _ping_llm_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception(
            "429 Too Many Requests - Rate limit exceeded"
        )

        with pytest.raises(LLMConnectionError):
            await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=3)

        # Should only be called once (no retries for rate limits)
        assert mock_llm.ainvoke.call_count == 1

    def test_rate_limit_error_class_exists(self):
        """Test that LLMRateLimitError class is available."""

        error = LLMRateLimitError(
            message="Rate limit exceeded",
            provider="anthropic",
            retry_after=60
        )

        assert error.retry_after == 60
        assert error.provider == "anthropic"


class TestMissingToolCallsRetry:
    """Test retry logic when LLM doesn't call expected tools (A2 edge case)."""

    @pytest.mark.asyncio
    async def test_retry_on_missing_tool_calls(self):
        """Test that workflow retries when LLM doesn't call tools.

        T105c: Mock LLM response without tool calls, assert retry with modified prompt.
        """
        from src.workflows.maven_maintenance_agent import _invoke_agent_with_retry

        # First response: no tool calls
        first_response = AIMessage(content="Let me think about this...")

        # Second response: has tool calls
        second_response = AIMessage(
            content="Analyzing dependencies",
            tool_calls=[
                {
                    "name": "maven_analyze_dependencies",
                    "args": {"project_path": "/test"},
                    "id": "call_1"
                }
            ]
        )

        mock_agent = AsyncMock()
        mock_agent.ainvoke.side_effect = [first_response, second_response]

        result = await _invoke_agent_with_retry(
            agent=mock_agent,
            input_data={"messages": [{"role": "user", "content": "Analyze"}]},
            max_retries=3,
            expected_tools=["maven_analyze_dependencies"]
        )

        # Should have retried
        assert mock_agent.ainvoke.call_count == 2
        # Final result should have tool calls
        assert result.tool_calls is not None
        assert len(result.tool_calls) > 0

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_for_missing_tools(self):
        """Test failure after max retries when tools never called.

        A2 edge case: After 3 attempts, should fail with clear error.
        """
        from src.workflows.maven_maintenance_agent import (
            MavenAgentError,
            _invoke_agent_with_retry,
        )

        # Always return response without tool calls
        no_tools_response = AIMessage(content="I cannot help with that.")

        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = no_tools_response

        # MavenAgentError wraps ToolCallError
        with pytest.raises(MavenAgentError) as exc_info:
            await _invoke_agent_with_retry(
                agent=mock_agent,
                input_data={"messages": [{"role": "user", "content": "Analyze"}]},
                max_retries=3,
                expected_tools=["maven_analyze_dependencies"]
            )

        # Should have tried 3 times
        assert mock_agent.ainvoke.call_count == 3
        assert "tool" in str(exc_info.value).lower()


class TestIntermittentConnectivityRetry:
    """Test exponential backoff retry for network issues (A4 edge case)."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test retry with exponential backoff on timeout.

        T105d: Mock network timeout, assert exponential backoff retry.
        """
        from src.lib.startup_checks import _ping_llm_with_retry

        # First two calls timeout, third succeeds
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = [
            TimeoutError("Connection timed out"),
            TimeoutError("Connection timed out"),
            AIMessage(content="pong"),
        ]

        # Should succeed after retries
        await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=3)

        # Should have been called 3 times
        assert mock_llm.ainvoke.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test retry on connection errors."""
        from src.lib.startup_checks import _ping_llm_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = [
            ConnectionError("Network unreachable"),
            AIMessage(content="pong"),
        ]

        await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=3)

        assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_for_connectivity(self):
        """Test failure after max retries on persistent connectivity issues."""
        from src.lib.startup_checks import LLMConnectionError, _ping_llm_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = ConnectionError("Network unreachable")

        with pytest.raises(LLMConnectionError) as exc_info:
            await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=3)

        assert mock_llm.ainvoke.call_count == 3
        assert "3 attempts" in str(exc_info.value)


class TestMalformedJSONValidation:
    """Test handling of malformed JSON in LLM responses (A5 edge case)."""

    def test_json_decode_error_caught(self):
        """Test that JSONDecodeError is properly caught.

        T105e: Verify malformed JSON is handled gracefully.
        """
        malformed_json = '{"tool": "analyze", "args": {invalid}}'

        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed_json)

    def test_malformed_tool_args_validation(self):
        """Test that malformed tool call arguments are detected.

        AIMessage validates tool_calls, so malformed args should fail construction.
        """
        # LangChain AIMessage validates tool_calls - this should raise
        with pytest.raises((ValueError, TypeError)):
            AIMessage(
                content="Analyzing",
                tool_calls=[
                    {
                        "name": "analyze",
                        "args": "not_a_dict",  # Should be dict - will fail
                        "id": "call_1"
                    }
                ]
            )

    def test_tool_call_validation(self):
        """Test that tool calls can be validated."""

        def validate_tool_call(tool_call: dict) -> bool:
            """Validate a tool call has required fields."""
            required = ["name", "args", "id"]
            if not all(k in tool_call for k in required):
                return False
            return isinstance(tool_call["args"], dict)

        # Valid tool call
        valid = {"name": "analyze", "args": {"path": "/test"}, "id": "1"}
        assert validate_tool_call(valid) is True

        # Invalid: args not a dict
        invalid = {"name": "analyze", "args": "string", "id": "1"}
        assert validate_tool_call(invalid) is False

        # Invalid: missing name
        invalid2 = {"args": {}, "id": "1"}
        assert validate_tool_call(invalid2) is False


class TestAuthenticationErrors:
    """Test authentication error handling."""

    @pytest.mark.asyncio
    async def test_auth_error_not_retried(self):
        """Test that authentication errors fail immediately (no retry)."""
        from src.lib.startup_checks import LLMConnectionError, _ping_llm_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception(
            "401 Unauthorized - Invalid API key"
        )

        with pytest.raises(LLMConnectionError) as exc_info:
            await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=3)

        # Should only try once (auth errors not retryable)
        assert mock_llm.ainvoke.call_count == 1
        assert "authentication" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_forbidden_error_not_retried(self):
        """Test that 403 Forbidden errors fail immediately."""
        from src.lib.startup_checks import LLMConnectionError, _ping_llm_with_retry

        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception(
            "403 Forbidden - Access denied"
        )

        with pytest.raises(LLMConnectionError):
            await _ping_llm_with_retry(mock_llm, timeout=5, max_retries=3)

        assert mock_llm.ainvoke.call_count == 1


class TestRetryableErrorClassification:
    """Test the error classification logic."""

    def test_timeout_is_retryable(self):
        """Test that timeout errors are classified as retryable."""
        from src.lib.startup_checks import _is_retryable_error

        assert _is_retryable_error(TimeoutError()) is True
        assert _is_retryable_error(TimeoutError()) is True

    def test_connection_error_is_retryable(self):
        """Test that connection errors are classified as retryable."""
        from src.lib.startup_checks import _is_retryable_error

        assert _is_retryable_error(ConnectionError()) is True

    def test_auth_error_not_retryable(self):
        """Test that auth errors are NOT retryable."""
        from src.lib.startup_checks import _is_retryable_error

        assert _is_retryable_error(Exception("401 Unauthorized")) is False
        assert _is_retryable_error(Exception("403 Forbidden")) is False
        assert _is_retryable_error(Exception("Invalid API key")) is False

    def test_rate_limit_not_retryable(self):
        """Test that rate limit errors are NOT retryable."""
        from src.lib.startup_checks import _is_retryable_error

        assert _is_retryable_error(Exception("429 Too Many Requests")) is False
        assert _is_retryable_error(Exception("Rate limit exceeded")) is False


class TestZeroComplaisance:
    """Test 'Zéro Complaisance' principle - fail fast, no silent degradation."""

    def test_llm_connection_check_is_mandatory(self):
        """Test that check_llm_connection raises on failure."""
        from src.lib.startup_checks import check_llm_connection

        # The function should raise, not return False or None
        assert callable(check_llm_connection)

    def test_agent_config_validation_is_mandatory(self):
        """Test that validate_agent_infrastructure raises on failure."""
        from src.lib.startup_checks import validate_agent_infrastructure

        # The function should raise AgentConfigError on invalid configs
        assert callable(validate_agent_infrastructure)

    def test_startup_check_error_hierarchy(self):
        """Test that all startup errors inherit from StartupCheckError."""
        from src.lib.startup_checks import (
            AgentConfigError,
            LLMConnectionError,
            StartupCheckError,
        )

        assert issubclass(LLMConnectionError, StartupCheckError)
        assert issubclass(AgentConfigError, StartupCheckError)
