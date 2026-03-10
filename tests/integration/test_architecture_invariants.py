"""Architecture invariant tests.

These tests validate that the critical architectural contracts between
components are maintained.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.tools import BaseTool


def _make_mock_tool(name: str) -> MagicMock:
    """Create a mock LangChain tool."""
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    tool.description = f"Mock tool: {name}"
    return tool


class TestPromptFilesExistForAllAgents:
    """Every agent YAML config must reference a prompt file that actually exists."""

    def test_all_agent_prompts_resolve_to_files(self):
        from src.agents.loader import AgentLoader

        loader = AgentLoader(config_dir="config/agents")
        agent_names = ["test_gen_agent"]

        for name in agent_names:
            config = loader.load_agent(name)
            prompt_path = config.prompts.system
            # prompt_path is like "config/prompts/testing/unit_test_strategy.md"
            from pathlib import Path

            assert Path(prompt_path).exists(), (
                f"Agent '{name}' references prompt '{prompt_path}' but file does not exist"
            )
