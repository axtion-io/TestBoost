"""Integration tests for agent configuration validation at startup (US3)."""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from src.lib.startup_checks import AgentConfigError, validate_agent_infrastructure


class TestAgentConfigValidation:
    """Test agent configuration infrastructure validation."""

    def test_validate_all_agents_success(self):
        """Test validation succeeds when all agent configs are valid."""
        # Should not raise any exception with real configs
        validate_agent_infrastructure()

    def test_missing_required_field_in_yaml(self, tmp_path, monkeypatch):
        """Test validation fails when required field is missing from YAML."""
        # Create temp config directory
        temp_config = tmp_path / "config"
        agents_dir = temp_config / "agents"
        agents_dir.mkdir(parents=True)

        # Copy valid agents
        real_config_dir = Path("config/agents")
        for agent_file in ["test_gen_agent.yaml", "deployment_agent.yaml"]:
            shutil.copy(real_config_dir / agent_file, agents_dir / agent_file)

        # Create YAML missing required 'llm' field
        incomplete_yaml = agents_dir / "maven_maintenance_agent.yaml"
        config_data = {
            "name": "maven_maintenance_agent",
            "description": "Test agent",
            "identity": {"role": "Test", "persona": "Test"},
            # Missing 'llm' field - required by Pydantic schema
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/maven/system_agent.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }
        incomplete_yaml.write_text(yaml.dump(config_data))

        # Change working directory to temp
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)

        try:
            # Should fail with validation error
            with pytest.raises(AgentConfigError) as exc_info:
                validate_agent_infrastructure()

            error_msg = str(exc_info.value)
            assert "maven_maintenance_agent" in error_msg
            assert "invalid" in error_msg.lower() or "validation" in error_msg.lower()
        finally:
            monkeypatch.chdir(original_cwd)

    def test_missing_prompt_file(self, tmp_path, monkeypatch):
        """Test validation fails when referenced prompt file doesn't exist."""
        # Create temp config directory with prompts
        temp_config = tmp_path / "config"
        agents_dir = temp_config / "agents"
        prompts_dir = temp_config / "prompts" / "maven"
        agents_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)

        # Copy valid agents (but with non-existent prompts)
        real_config_dir = Path("config/agents")

        # Create agent with non-existent prompt reference
        config_data = {
            "name": "maven_maintenance_agent",
            "description": "Test agent",
            "identity": {"role": "Test", "persona": "Test"},
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "temperature": 0.3},
            "tools": {"mcp_servers": ["maven-maintenance"]},
            "prompts": {"system": "config/prompts/maven/nonexistent_prompt.md"},  # Doesn't exist
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }
        agent_file = agents_dir / "maven_maintenance_agent.yaml"
        agent_file.write_text(yaml.dump(config_data))

        # Copy other valid agents
        for agent_file_name in ["test_gen_agent.yaml", "deployment_agent.yaml"]:
            shutil.copy(real_config_dir / agent_file_name, agents_dir / agent_file_name)

        # Change working directory to temp
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)

        try:
            # Should fail because prompt doesn't exist
            with pytest.raises(AgentConfigError) as exc_info:
                validate_agent_infrastructure()

            error_msg = str(exc_info.value)
            assert "maven_maintenance_agent" in error_msg
            assert "missing prompt" in error_msg.lower() or "nonexistent_prompt" in error_msg.lower()
        finally:
            monkeypatch.chdir(original_cwd)

    def test_unregistered_mcp_server(self, tmp_path, monkeypatch):
        """Test validation fails when agent references unregistered MCP server."""
        # Create temp config directory
        temp_config = tmp_path / "config"
        agents_dir = temp_config / "agents"
        prompts_dir = temp_config / "prompts" / "maven"
        agents_dir.mkdir(parents=True)
        prompts_dir.mkdir(parents=True)

        # Create a valid prompt file
        prompt_file = prompts_dir / "system_agent.md"
        prompt_file.write_text("Test prompt")

        # Create valid YAML but with unregistered MCP server
        config_data = {
            "name": "maven_maintenance_agent",
            "description": "Test agent",
            "identity": {"role": "Test", "persona": "Test"},
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "temperature": 0.3},
            "tools": {"mcp_servers": ["nonexistent-mcp-server"]},  # Not registered
            "prompts": {"system": "config/prompts/maven/system_agent.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }
        agent_file = agents_dir / "maven_maintenance_agent.yaml"
        agent_file.write_text(yaml.dump(config_data))

        # Copy other agents
        real_config_dir = Path("config/agents")
        for agent_file_name in ["test_gen_agent.yaml", "deployment_agent.yaml"]:
            shutil.copy(real_config_dir / agent_file_name, agents_dir / agent_file_name)

        # Change working directory to temp
        original_cwd = Path.cwd()
        monkeypatch.chdir(tmp_path)

        try:
            # Should fail because MCP server not registered
            with pytest.raises(AgentConfigError) as exc_info:
                validate_agent_infrastructure()

            error_msg = str(exc_info.value)
            assert "maven_maintenance_agent" in error_msg
            assert "unregistered" in error_msg.lower() or "nonexistent-mcp-server" in error_msg.lower()
        finally:
            monkeypatch.chdir(original_cwd)
