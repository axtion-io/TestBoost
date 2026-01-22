"""Startup validation checks for TestBoost application."""

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage

from src.lib.config import get_settings
from src.lib.llm import LLMError, LLMProviderError, LLMTimeoutError, get_llm
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Startup check timeout (5 seconds max)
STARTUP_TIMEOUT = 5

# Retry configuration for intermittent errors (A4 edge case)
MAX_RETRIES = 3
MIN_WAIT = 1  # seconds
MAX_WAIT = 10  # seconds


class StartupCheckError(Exception):
    """Base exception for startup check failures."""

    pass


class LLMConnectionError(StartupCheckError):
    """Raised when LLM connection check fails."""

    pass


class AgentConfigError(StartupCheckError):
    """Raised when agent configuration validation fails."""

    pass


def _is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an error is retryable.

    Retryable errors (A4 edge case):
    - TimeoutError, asyncio.TimeoutError
    - ConnectionError
    - Network-related errors

    Non-retryable errors (fail immediately):
    - AuthenticationError (401, 403)
    - Invalid API key errors
    - Rate limit errors (429) - A1 edge case
    - Provider configuration errors

    Args:
        exception: Exception to check

    Returns:
        True if error should be retried, False otherwise
    """
    # Check if it's a timeout error
    if isinstance(exception, TimeoutError | asyncio.TimeoutError | LLMTimeoutError):
        return True

    # Check if it's a connection error
    if isinstance(exception, ConnectionError):
        return True

    # Check error message for authentication/auth errors (non-retryable)
    error_msg = str(exception).lower()
    if any(
        keyword in error_msg
        for keyword in ["401", "403", "unauthorized", "forbidden", "invalid api key"]
    ):
        return False

    # Check for rate limit errors (non-retryable, A1 edge case)
    if "429" in error_msg or "rate limit" in error_msg:
        return False

    # Check for provider configuration errors (non-retryable)
    # Default: retry for unknown errors (not configuration related)
    return "not configured" not in error_msg and "missing" not in error_msg


async def _ping_llm_with_retry(
    llm: Any, timeout: int = STARTUP_TIMEOUT, max_retries: int = MAX_RETRIES
) -> None:
    """
    Ping LLM with retry logic for intermittent connectivity (A4 edge case).

    Args:
        llm: LLM instance to ping
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Raises:
        LLMConnectionError: If ping fails after retries
        asyncio.TimeoutError: If request times out
    """
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            # Send minimal ping message
            messages = [HumanMessage(content="ping")]

            # Invoke with timeout
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout)

            if response is None:
                raise LLMConnectionError("LLM returned None response")

            logger.debug("llm_ping_success", response_length=len(str(response)), attempt=attempt)
            return  # Success!

        except TimeoutError as e:
            logger.warning(
                "llm_ping_timeout", timeout=timeout, attempt=attempt, max_retries=max_retries
            )
            last_error = LLMTimeoutError(f"LLM ping timed out after {timeout}s")

            # Retry on timeout
            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), MAX_WAIT)
                logger.info("llm_ping_retry", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise last_error from e

        except ConnectionError as e:
            logger.warning(
                "llm_ping_connection_error", error=str(e), attempt=attempt, max_retries=max_retries
            )
            last_error = e

            # Retry on connection errors
            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), MAX_WAIT)
                logger.info("llm_ping_retry", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise LLMConnectionError(f"LLM ping failed after {max_retries} attempts: {e}") from e

        except Exception as e:
            # Check for rate limit errors (A1 edge case)
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                # Extract retry-after if present
                retry_after = "unknown"
                if "retry after" in error_msg.lower():
                    # Try to extract number from error message
                    import re

                    match = re.search(r"retry after (\d+)", error_msg, re.IGNORECASE)
                    if match:
                        retry_after = f"{match.group(1)} seconds"

                logger.error("llm_rate_limited", retry_after=retry_after, error=error_msg)
                raise LLMConnectionError(
                    f"LLM rate limit exceeded. Retry after {retry_after}. " f"Error: {error_msg}"
                ) from e

            # Check for authentication errors (non-retryable)
            if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg.lower():
                logger.error("llm_auth_failed", error=error_msg)
                raise LLMConnectionError(f"LLM authentication failed: {error_msg}") from e

            # Re-raise as LLMConnectionError
            logger.error("llm_ping_failed", error=str(e), error_type=type(e).__name__)
            raise LLMConnectionError(f"LLM ping failed: {e}") from e


async def check_llm_connection(model: str | None = None) -> None:
    """
    Check LLM provider connectivity at startup.

    Implements:
    - T015: Ping configured LLM provider
    - T016: Error handling for missing API keys (raise LLMProviderError)
    - T017: Error handling for invalid API keys (raise AuthenticationError)
    - T018: Timeout handling (5 second max, raise TimeoutError)
    - T019: Retry logic with exponential backoff for intermittent connectivity (A4: 3 attempts, 1s-10s wait)
    - T020: Rate limit error detection (catch 429, extract retry-after, fail with clear message) (A1)

    Constitutional principle: "Zéro Complaisance" - No workflows execute without LLM.

    Args:
        model: Optional model override (defaults to settings.model)

    Raises:
        LLMProviderError: If API key not configured
        LLMConnectionError: If connection fails after retries
        LLMTimeoutError: If ping times out

    Example:
        >>> await check_llm_connection()
        # Logs: llm_connection_ok

        >>> await check_llm_connection(model="anthropic/claude-3-sonnet")
        # Logs: llm_connection_ok with custom model
    """
    try:
        logger.info("llm_connection_check_start", model=model or settings.model)

        # Get LLM instance (T016: raises LLMProviderError if API key missing)
        llm = get_llm(model=model, timeout=STARTUP_TIMEOUT)

        # Ping LLM with retry logic (T019: A4 edge case)
        await _ping_llm_with_retry(llm, timeout=STARTUP_TIMEOUT)

        logger.info("llm_connection_ok", model=model or settings.model)

    except LLMProviderError as e:
        # T016: Missing API key
        logger.error("llm_connection_failed", reason="missing_api_key", error=str(e))
        raise

    except LLMConnectionError as e:
        # T017, T020: Auth errors, rate limits
        logger.error("llm_connection_failed", reason="connection_error", error=str(e))
        raise LLMError(f"LLM not available: {e}") from e

    except LLMTimeoutError as e:
        # T018: Timeout
        logger.error("llm_connection_failed", reason="timeout", error=str(e))
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(
            "llm_connection_failed", reason="unexpected", error=str(e), error_type=type(e).__name__
        )
        raise LLMError(f"LLM connection check failed: {e}") from e


def validate_agent_infrastructure() -> None:
    """
    Validate agent configuration infrastructure at startup.

    Implements US3: Agent Configuration Management
    - T084-T093: Validate all agent YAML configs exist and are valid
    - Validate referenced prompts exist
    - Validate MCP servers are registered

    Raises:
        AgentConfigError: If any agent config is invalid or missing
    """
    from pathlib import Path

    from pydantic import ValidationError

    from src.agents.loader import AgentLoader
    from src.mcp_servers.registry import TOOL_REGISTRY

    logger.info("agent_infrastructure_check_start")

    # List of critical agents that MUST be valid at startup
    REQUIRED_AGENTS = [
        "maven_maintenance_agent",
        "test_gen_agent",
        "deployment_agent",
    ]

    loader = AgentLoader("config/agents")
    validated_agents = []
    errors = []

    for agent_name in REQUIRED_AGENTS:
        try:
            logger.info("validating_agent_config", agent=agent_name)

            # T084: Load and validate agent YAML
            config = loader.load_agent(agent_name)

            logger.info(
                "agent_config_valid",
                agent=config.name,
                llm_provider=config.llm.provider,
                llm_model=config.llm.model,
                mcp_servers=config.tools.mcp_servers,
            )

            # T085: Validate system prompt exists
            prompt_path = Path(config.prompts.system)
            if not prompt_path.exists():
                error_msg = (
                    f"Agent '{agent_name}' references missing prompt: {config.prompts.system}"
                )
                logger.error("agent_prompt_missing", agent=agent_name, prompt=config.prompts.system)
                errors.append(error_msg)
                continue

            logger.info("agent_prompt_valid", agent=agent_name, prompt=config.prompts.system)

            # T086: Validate MCP servers are registered
            for server_name in config.tools.mcp_servers:
                if server_name not in TOOL_REGISTRY:
                    error_msg = (
                        f"Agent '{agent_name}' references unregistered MCP server: {server_name}"
                    )
                    logger.error(
                        "agent_mcp_server_missing",
                        agent=agent_name,
                        server=server_name,
                        registered_servers=list(TOOL_REGISTRY.keys()),
                    )
                    errors.append(error_msg)
                    continue

            validated_agents.append(agent_name)

        except FileNotFoundError as e:
            error_msg = f"Agent configuration file not found: {agent_name}.yaml"
            logger.error("agent_config_not_found", agent=agent_name, error=str(e))
            errors.append(error_msg)

        except ValidationError as e:
            error_msg = f"Agent configuration invalid: {agent_name} - {str(e)}"
            logger.error("agent_config_invalid", agent=agent_name, error=str(e))
            errors.append(error_msg)

        except Exception as e:
            error_msg = f"Agent validation failed: {agent_name} - {str(e)}"
            logger.error(
                "agent_validation_error",
                agent=agent_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            errors.append(error_msg)

    # Report results
    if errors:
        logger.error(
            "agent_infrastructure_check_failed",
            validated=len(validated_agents),
            failed=len(errors),
            errors=errors,
        )
        error_summary = "\n".join(f"  - {err}" for err in errors)
        raise AgentConfigError(
            f"Agent infrastructure validation failed ({len(errors)} errors):\n{error_summary}"
        )

    logger.info(
        "agent_infrastructure_check_complete",
        validated_agents=validated_agents,
        count=len(validated_agents),
    )


class DatabaseConnectionError(StartupCheckError):
    """Raised when database connection check fails."""

    pass


class MCPRegistryError(StartupCheckError):
    """Raised when MCP tool registry validation fails."""

    pass


async def check_database_connection() -> None:
    """
    Check database connectivity at startup.

    Verifies that the PostgreSQL database is reachable and responding.

    Raises:
        DatabaseConnectionError: If database is not accessible
    """
    from src.lib.database import check_connection_health

    logger.info("database_connection_check_start")

    try:
        is_healthy = await check_connection_health()

        if not is_healthy:
            raise DatabaseConnectionError("Database health check returned unhealthy status")

        logger.info("database_connection_ok")

    except DatabaseConnectionError:
        raise

    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise DatabaseConnectionError(f"Database connection check failed: {e}") from e


def validate_mcp_registry() -> None:
    """
    Validate MCP tool registry at startup.

    Verifies that all required MCP servers are registered and can provide tools.

    Raises:
        MCPRegistryError: If any required MCP server is missing or invalid
    """
    from src.mcp_servers.registry import TOOL_REGISTRY, list_available_servers

    logger.info("mcp_registry_check_start")

    # Required MCP servers for core functionality
    REQUIRED_SERVERS = [
        "maven-maintenance",
        "test-generator",
        "docker-deployment",
        "git-maintenance",
    ]

    available_servers = list_available_servers()
    missing_servers = []
    invalid_servers = []

    for server_name in REQUIRED_SERVERS:
        if server_name not in available_servers:
            missing_servers.append(server_name)
            continue

        # Try to get tools to verify the server is functional
        try:
            getter = TOOL_REGISTRY.get(server_name)
            if getter:
                tools = getter()
                if not tools:
                    invalid_servers.append(f"{server_name} (no tools returned)")
                else:
                    logger.debug(
                        "mcp_server_valid",
                        server=server_name,
                        tool_count=len(tools),
                    )
        except Exception as e:
            invalid_servers.append(f"{server_name} (error: {e})")

    if missing_servers or invalid_servers:
        error_parts = []
        if missing_servers:
            error_parts.append(f"Missing servers: {', '.join(missing_servers)}")
        if invalid_servers:
            error_parts.append(f"Invalid servers: {', '.join(invalid_servers)}")

        error_msg = "; ".join(error_parts)
        logger.error("mcp_registry_check_failed", error=error_msg)
        raise MCPRegistryError(f"MCP registry validation failed: {error_msg}")

    logger.info(
        "mcp_registry_check_complete",
        registered_servers=available_servers,
        count=len(available_servers),
    )


async def run_all_startup_checks(skip_db: bool = False) -> None:
    """
    Run all startup validation checks.

    Args:
        skip_db: Skip database connectivity check (useful for CLI commands)

    Raises:
        StartupCheckError: If any check fails
    """
    logger.info("startup_checks_begin")
    checks_passed = 0

    try:
        # Check 1: LLM connectivity (US1)
        await check_llm_connection()
        checks_passed += 1

        # Check 2: Agent configuration validation (US3)
        validate_agent_infrastructure()
        checks_passed += 1

        # Check 3: Database connectivity
        if not skip_db:
            await check_database_connection()
            checks_passed += 1

        # Check 4: MCP tool registry validation
        validate_mcp_registry()
        checks_passed += 1

        logger.info("startup_checks_complete", checks_passed=checks_passed)

    except Exception as e:
        logger.error("startup_checks_failed", error=str(e), checks_passed=checks_passed)
        raise StartupCheckError(f"Startup checks failed: {e}") from e


__all__ = [
    "check_llm_connection",
    "check_database_connection",
    "validate_agent_infrastructure",
    "validate_mcp_registry",
    "run_all_startup_checks",
    "StartupCheckError",
    "LLMConnectionError",
    "AgentConfigError",
    "DatabaseConnectionError",
    "MCPRegistryError",
]
