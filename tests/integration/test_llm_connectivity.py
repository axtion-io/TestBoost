"""Integration tests for LLM connectivity validation at startup."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.lib.llm import LLMError, LLMProviderError, LLMTimeoutError
from src.lib.startup_checks import check_llm_connection


class TestLLMConnectionSuccess:
    """Test successful LLM connection scenarios."""

    @pytest.mark.asyncio
    async def test_llm_connection_success(self):
        """Test successful LLM connection with valid API key."""
        # Mock successful LLM response
        mock_response = AIMessage(content="pong")

        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            # Should not raise any exception
            await check_llm_connection()

            # Verify LLM was called with ping message
            mock_llm.ainvoke.assert_called_once()
            call_args = mock_llm.ainvoke.call_args[0][0]
            assert len(call_args) == 1
            # call_args[0] is a HumanMessage object
            assert hasattr(call_args[0], "content")
            assert "ping" in call_args[0].content.lower()

    @pytest.mark.asyncio
    async def test_llm_connection_with_custom_model(self):
        """Test LLM connection with custom model override."""
        mock_response = AIMessage(content="pong")

        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            await check_llm_connection(model="anthropic/claude-sonnet-4-5")

            # Verify get_llm called with custom model
            mock_get_llm.assert_called_once_with(
                model="anthropic/claude-sonnet-4-5",
                timeout=5
            )


class TestLLMConnectionFailure:
    """Test LLM connection failure scenarios."""

    @pytest.mark.asyncio
    async def test_llm_connection_missing_api_key(self):
        """Test connection fails with missing API key."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_get_llm.side_effect = LLMProviderError("GOOGLE_API_KEY not configured")

            with pytest.raises(LLMProviderError) as exc_info:
                await check_llm_connection()

            assert "GOOGLE_API_KEY not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_llm_connection_invalid_api_key(self):
        """Test connection fails with invalid API key."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            # Simulate authentication error (401)
            mock_llm.ainvoke.side_effect = Exception("401 Unauthorized: Invalid API key")
            mock_get_llm.return_value = mock_llm

            with pytest.raises(LLMError) as exc_info:
                await check_llm_connection()

            assert "Invalid API key" in str(exc_info.value) or "401" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_llm_connection_rate_limit(self):
        """Test connection fails with rate limit error (A1 edge case)."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            # Simulate rate limit error (429)
            rate_limit_error = Exception("429 Too Many Requests: Rate limit exceeded. Retry after 60 seconds")
            mock_llm.ainvoke.side_effect = rate_limit_error
            mock_get_llm.return_value = mock_llm

            with pytest.raises(LLMError) as exc_info:
                await check_llm_connection()

            error_msg = str(exc_info.value)
            assert "429" in error_msg or "Rate limit" in error_msg

    @pytest.mark.asyncio
    async def test_llm_connection_network_error(self):
        """Test connection fails with network error."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.side_effect = ConnectionError("Failed to connect to LLM provider")
            mock_get_llm.return_value = mock_llm

            with pytest.raises(LLMError) as exc_info:
                await check_llm_connection()

            assert "Failed to connect" in str(exc_info.value) or "Connection" in str(exc_info.value)


class TestLLMConnectionTimeout:
    """Test LLM connection timeout scenarios."""

    @pytest.mark.asyncio
    async def test_llm_connection_timeout(self):
        """Test connection times out after 5 seconds."""
        import asyncio

        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()

            # Simulate timeout by sleeping longer than timeout
            async def slow_response(*args, **kwargs):
                await asyncio.sleep(10)  # 10 seconds > 5 second timeout
                return AIMessage(content="pong")

            mock_llm.ainvoke.side_effect = slow_response
            mock_get_llm.return_value = mock_llm

            with pytest.raises((LLMTimeoutError, asyncio.TimeoutError)) as exc_info:
                await check_llm_connection()

            # Verify error mentions timeout
            error_msg = str(exc_info.value)
            assert "timeout" in error_msg.lower() or "timed out" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_llm_connection_retry_on_timeout(self):
        """Test connection retries on timeout (A4 edge case)."""
        import asyncio

        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()

            # First two calls timeout, third succeeds
            call_count = 0
            async def intermittent_timeout(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise asyncio.TimeoutError("Request timed out")
                return AIMessage(content="pong")

            mock_llm.ainvoke.side_effect = intermittent_timeout
            mock_get_llm.return_value = mock_llm

            # Should succeed after retries
            await check_llm_connection()

            # Verify it retried 3 times total (2 failures + 1 success)
            assert call_count == 3


class TestLLMConnectionRetry:
    """Test LLM connection retry logic (A4 edge case)."""

    @pytest.mark.asyncio
    async def test_llm_connection_retry_on_network_error(self):
        """Test connection retries on intermittent network errors."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()

            # First two calls fail with network error, third succeeds
            call_count = 0
            async def intermittent_network_error(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise ConnectionError("Network unreachable")
                return AIMessage(content="pong")

            mock_llm.ainvoke.side_effect = intermittent_network_error
            mock_get_llm.return_value = mock_llm

            # Should succeed after retries
            await check_llm_connection()

            # Verify it retried (exact count depends on retry logic)
            assert call_count >= 2

    @pytest.mark.asyncio
    async def test_llm_connection_retry_exhausted(self):
        """Test connection fails after exhausting retries."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()

            # Always fail
            mock_llm.ainvoke.side_effect = ConnectionError("Network unreachable")
            mock_get_llm.return_value = mock_llm

            with pytest.raises(LLMError):
                await check_llm_connection()

    @pytest.mark.asyncio
    async def test_llm_connection_no_retry_on_auth_error(self):
        """Test connection does NOT retry on authentication errors."""
        with patch("src.lib.startup_checks.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()

            # Auth error should not retry
            call_count = 0
            async def auth_error(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                raise Exception("401 Unauthorized: Invalid API key")

            mock_llm.ainvoke.side_effect = auth_error
            mock_get_llm.return_value = mock_llm

            with pytest.raises(LLMError):
                await check_llm_connection()

            # Should fail immediately without retries (call count = 1)
            assert call_count == 1
