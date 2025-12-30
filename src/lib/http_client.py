"""HTTP client wrapper with configurable timeouts (CHK047).

Provides a consistent HTTP client with proper timeout handling
for all external API calls.
"""

from typing import Any

import httpx

from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# Default timeout values by operation type
DEFAULT_TIMEOUTS = {
    "connect": 10.0,      # Connection timeout
    "read": 30.0,         # Read timeout for most operations
    "write": 30.0,        # Write timeout
    "pool": 10.0,         # Connection pool timeout
}

# Extended timeouts for long-running operations
EXTENDED_TIMEOUTS = {
    "connect": 10.0,
    "read": 120.0,        # Extended read timeout
    "write": 60.0,
    "pool": 10.0,
}


class TimeoutConfig:
    """Timeout configuration for HTTP requests."""

    def __init__(
        self,
        connect: float = DEFAULT_TIMEOUTS["connect"],
        read: float = DEFAULT_TIMEOUTS["read"],
        write: float = DEFAULT_TIMEOUTS["write"],
        pool: float = DEFAULT_TIMEOUTS["pool"],
    ):
        """
        Initialize timeout configuration.

        Args:
            connect: Connection establishment timeout in seconds
            read: Read operation timeout in seconds
            write: Write operation timeout in seconds
            pool: Connection pool timeout in seconds
        """
        self.connect = connect
        self.read = read
        self.write = write
        self.pool = pool

    def to_httpx(self) -> httpx.Timeout:
        """Convert to httpx Timeout object."""
        return httpx.Timeout(
            connect=self.connect,
            read=self.read,
            write=self.write,
            pool=self.pool,
        )


# Preset timeout configurations
TIMEOUT_PRESETS = {
    "default": TimeoutConfig(),
    "extended": TimeoutConfig(**EXTENDED_TIMEOUTS),
    "quick": TimeoutConfig(connect=5.0, read=10.0, write=10.0, pool=5.0),
    "llm": TimeoutConfig(connect=10.0, read=settings.llm_timeout, write=30.0, pool=10.0),
}


class HTTPClient:
    """
    HTTP client wrapper with configurable timeouts.

    Provides a consistent interface for making HTTP requests with
    proper timeout handling and error logging.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: TimeoutConfig | str = "default",
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            timeout: Timeout configuration or preset name
            headers: Default headers for all requests
        """
        if isinstance(timeout, str):
            timeout = TIMEOUT_PRESETS.get(timeout, TIMEOUT_PRESETS["default"])

        self._timeout = timeout
        self._base_url = base_url
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async client."""
        if self._client is None or self._client.is_closed:
            # Build kwargs, only include base_url if set
            client_kwargs: dict[str, Any] = {
                "timeout": self._timeout.to_httpx(),
                "headers": self._headers,
            }
            if self._base_url:
                client_kwargs["base_url"] = self._base_url
            self._client = httpx.AsyncClient(**client_kwargs)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: TimeoutConfig | str | None = None,
    ) -> httpx.Response:
        """
        Make a GET request.

        Args:
            url: URL path (relative to base_url if set)
            params: Query parameters
            headers: Additional headers
            timeout: Override timeout for this request

        Returns:
            HTTP response

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPError: For other HTTP errors
        """
        client = await self._get_client()
        request_timeout = self._resolve_timeout(timeout)

        logger.debug("http_get_request", url=url, params=params)

        try:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=request_timeout,
            )
            logger.debug(
                "http_get_response",
                url=url,
                status_code=response.status_code,
            )
            return response
        except httpx.TimeoutException as e:
            logger.error("http_get_timeout", url=url, error=str(e))
            raise
        except httpx.HTTPError as e:
            logger.error("http_get_error", url=url, error=str(e))
            raise

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: TimeoutConfig | str | None = None,
    ) -> httpx.Response:
        """
        Make a POST request.

        Args:
            url: URL path (relative to base_url if set)
            json: JSON body
            data: Form data
            headers: Additional headers
            timeout: Override timeout for this request

        Returns:
            HTTP response
        """
        client = await self._get_client()
        request_timeout = self._resolve_timeout(timeout)

        logger.debug("http_post_request", url=url)

        try:
            response = await client.post(
                url,
                json=json,
                data=data,
                headers=headers,
                timeout=request_timeout,
            )
            logger.debug(
                "http_post_response",
                url=url,
                status_code=response.status_code,
            )
            return response
        except httpx.TimeoutException as e:
            logger.error("http_post_timeout", url=url, error=str(e))
            raise
        except httpx.HTTPError as e:
            logger.error("http_post_error", url=url, error=str(e))
            raise

    async def put(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: TimeoutConfig | str | None = None,
    ) -> httpx.Response:
        """Make a PUT request."""
        client = await self._get_client()
        request_timeout = self._resolve_timeout(timeout)

        try:
            return await client.put(
                url,
                json=json,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as e:
            logger.error("http_put_timeout", url=url, error=str(e))
            raise

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: TimeoutConfig | str | None = None,
    ) -> httpx.Response:
        """Make a DELETE request."""
        client = await self._get_client()
        request_timeout = self._resolve_timeout(timeout)

        try:
            return await client.delete(
                url,
                headers=headers,
                timeout=request_timeout,
            )
        except httpx.TimeoutException as e:
            logger.error("http_delete_timeout", url=url, error=str(e))
            raise

    def _resolve_timeout(self, timeout: TimeoutConfig | str | None) -> httpx.Timeout | None:
        """Resolve timeout to httpx.Timeout object."""
        if timeout is None:
            return None
        if isinstance(timeout, str):
            return TIMEOUT_PRESETS.get(timeout, TIMEOUT_PRESETS["default"]).to_httpx()
        return timeout.to_httpx()

    async def __aenter__(self) -> "HTTPClient":
        """Context manager entry."""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Context manager exit."""
        await self.close()


# Convenience function for creating clients
def create_client(
    base_url: str | None = None,
    timeout: str = "default",
    headers: dict[str, str] | None = None,
) -> HTTPClient:
    """
    Create an HTTP client with the specified configuration.

    Args:
        base_url: Base URL for requests
        timeout: Timeout preset name
        headers: Default headers

    Returns:
        Configured HTTPClient instance
    """
    return HTTPClient(base_url=base_url, timeout=timeout, headers=headers)


__all__ = [
    "HTTPClient",
    "TimeoutConfig",
    "TIMEOUT_PRESETS",
    "create_client",
]
