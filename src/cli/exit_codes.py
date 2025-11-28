"""CLI exit codes for consistent error reporting.

Exit codes per quickstart.md specification:
| Code | Meaning                    | Recommended Action                         |
|------|----------------------------|--------------------------------------------|
| 0    | Success                    | -                                          |
| 1    | General error              | Check logs                                 |
| 2    | Invalid arguments          | Check command syntax                       |
| 3    | Project not found          | Check project path                         |
| 4    | Project locked             | Wait or cancel existing session            |
| 5    | Baseline tests failed      | Fix existing tests                         |
| 6    | LLM error                  | Check credentials and quotas               |
| 7    | Docker error               | Check Docker is running                    |
| 8    | Timeout                    | Increase timeout or simplify operation     |
"""


class ExitCode:
    """Standard exit codes for TestBoost CLI per quickstart.md."""

    SUCCESS = 0
    """Command completed successfully."""

    ERROR = 1
    """General error occurred. Check logs for details."""

    INVALID_ARGS = 2
    """Invalid arguments provided. Check command syntax."""

    PROJECT_NOT_FOUND = 3
    """Project not found. Check the project path."""

    PROJECT_LOCKED = 4
    """Project is locked by another session. Wait or cancel existing session."""

    BASELINE_TESTS_FAILED = 5
    """Baseline tests failed before maintenance. Fix existing tests first."""

    LLM_ERROR = 6
    """LLM provider error. Check credentials and API quotas."""

    DOCKER_ERROR = 7
    """Docker error. Check that Docker is running."""

    TIMEOUT = 8
    """Operation timed out. Increase timeout or simplify the operation."""

    # Additional codes for internal use
    WORKFLOW_ERROR = 10
    """Workflow execution error."""

    BUILD_FAILED = 20
    """Maven build failed."""

    CONFIG_ERROR = 30
    """Configuration error."""

    CONNECTION_ERROR = 31
    """Connection error (database, API, etc.)."""

    PERMISSION_DENIED = 32
    """Permission denied."""

    CANCELLED = 33
    """Operation was cancelled by user."""


# Convenience exports for common codes
SUCCESS = ExitCode.SUCCESS
ERROR = ExitCode.ERROR
INVALID_ARGS = ExitCode.INVALID_ARGS
PROJECT_NOT_FOUND = ExitCode.PROJECT_NOT_FOUND
PROJECT_LOCKED = ExitCode.PROJECT_LOCKED
BASELINE_TESTS_FAILED = ExitCode.BASELINE_TESTS_FAILED
LLM_ERROR = ExitCode.LLM_ERROR
DOCKER_ERROR = ExitCode.DOCKER_ERROR
TIMEOUT = ExitCode.TIMEOUT


def get_exit_code_description(code: int) -> str:
    """
    Get a human-readable description for an exit code.

    Args:
        code: Exit code number

    Returns:
        Description string
    """
    descriptions = {
        0: "Success",
        1: "General error - check logs",
        2: "Invalid arguments - check command syntax",
        3: "Project not found - check project path",
        4: "Project locked - wait or cancel existing session",
        5: "Baseline tests failed - fix existing tests",
        6: "LLM error - check credentials and quotas",
        7: "Docker error - check Docker is running",
        8: "Timeout - increase timeout or simplify operation",
        10: "Workflow execution error",
        20: "Maven build failed",
        30: "Configuration error",
        31: "Connection error",
        32: "Permission denied",
        33: "Cancelled by user",
    }
    return descriptions.get(code, f"Unknown exit code: {code}")


__all__ = [
    "ExitCode",
    "SUCCESS",
    "ERROR",
    "INVALID_ARGS",
    "PROJECT_NOT_FOUND",
    "PROJECT_LOCKED",
    "BASELINE_TESTS_FAILED",
    "LLM_ERROR",
    "DOCKER_ERROR",
    "TIMEOUT",
    "get_exit_code_description",
]
