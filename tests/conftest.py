"""Pytest configuration and fixtures for TestBoost tests.

Sets up mocks for external dependencies to allow testing of isolated functions.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock


# Mock all external dependencies before importing the test_generation_agent module
# This allows us to test pure functions like _parse_test_failures without loading
# the entire application stack


def _setup_mocks():
    """Set up mock modules for dependencies not available in test environment."""
    # Mock modules that may not be available in the worktree
    mock_modules = [
        "src",
        "src.agents",
        "src.agents.loader",
        "src.db",
        "src.db.repository",
        "src.lib",
        "src.lib.agent_retry",
        "src.lib.config",
        "src.lib.llm",
        "src.lib.logging",
        "src.mcp_servers",
        "src.mcp_servers.registry",
        "src.mcp_servers.test_generator",
        "src.mcp_servers.test_generator.tools",
        "src.mcp_servers.test_generator.tools.generate_unit",
        "src.models",
        "src.models.impact",
        "langchain_core",
        "langchain_core.messages",
        "langgraph",
        "langgraph.prebuilt",
    ]

    for module_name in mock_modules:
        if module_name not in sys.modules:
            mock_module = MagicMock()
            # Special handling for specific modules
            if module_name == "src.lib.logging":
                mock_module.get_logger = MagicMock(return_value=MagicMock())
            elif module_name == "src.lib.config":
                mock_module.get_settings = MagicMock(return_value=MagicMock())
            elif module_name == "langchain_core.messages":
                mock_module.AIMessage = MagicMock
                mock_module.HumanMessage = MagicMock
            sys.modules[module_name] = mock_module


# Set up mocks before any imports
_setup_mocks()

# Now add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
