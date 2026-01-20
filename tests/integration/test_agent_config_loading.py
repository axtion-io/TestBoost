"""Integration tests for agent YAML configuration loading (US3 - T079-T082).

Tests for User Story 3: Agent Configuration Management.
Validates that YAML configs load correctly and changes take effect.
"""

import shutil
from pathlib import Path

import pytest
import yaml

from src.agents.loader import AgentConfig, AgentLoader


class TestYAMLConfigLoading:
    """Test YAML configuration loading functionality (T079)."""

    def test_yaml_config_loads(self):
        """Test that all 3 agent YAML configs load successfully (T079).

        Assert 3 YAML configs loaded (maven_maintenance, test_gen, deployment),
        assert each config has 'model', 'temperature', 'max_tokens' keys,
        assert model names valid.
        """
        loader = AgentLoader(config_dir="config/agents")

        # Load all 3 required agent configs
        agent_names = ["maven_maintenance_agent", "test_gen_agent", "deployment_agent"]

        loaded_configs = {}
        for name in agent_names:
            config = loader.load_agent(name)
            loaded_configs[name] = config

        # Assert all 3 configs loaded
        assert len(loaded_configs) == 3, f"Expected 3 configs, got {len(loaded_configs)}"

        # Validate each config has required LLM keys
        valid_providers = ["google-genai", "anthropic", "openai"]

        for name, config in loaded_configs.items():
            # Assert config is valid AgentConfig instance
            assert isinstance(config, AgentConfig), f"{name} is not AgentConfig"

            # Assert 'model' exists and is non-empty
            assert config.llm.model, f"{name} missing 'model'"
            assert len(config.llm.model) > 0, f"{name} has empty 'model'"

            # Assert 'temperature' exists and is valid
            assert config.llm.temperature is not None, f"{name} missing 'temperature'"
            assert (
                0.0 <= config.llm.temperature <= 2.0
            ), f"{name} temperature {config.llm.temperature} out of range [0, 2]"

            # Assert 'max_tokens' exists (can be None for default)
            # max_tokens is optional but should be accessible
            _ = config.llm.max_tokens  # Just verify it's accessible

            # Assert provider is valid
            assert (
                config.llm.provider in valid_providers
            ), f"{name} has invalid provider '{config.llm.provider}'"


class TestYAMLChangesEffect:
    """Test that YAML config changes take effect on reload (T080)."""

    def test_yaml_changes_take_effect(self, tmp_path):
        """Test that modifying temperature in YAML takes effect on reload (T080).

        Modify temperature in YAML, reload config, assert new temperature
        applied to agent, restore original YAML after test.
        """
        # Setup: copy real config to temp directory
        real_config_dir = Path("config/agents")
        temp_config_dir = tmp_path / "agents"
        temp_config_dir.mkdir(parents=True)

        # Copy all agent configs
        for yaml_file in real_config_dir.glob("*.yaml"):
            shutil.copy(yaml_file, temp_config_dir / yaml_file.name)

        # Create loader with temp config
        loader = AgentLoader(config_dir=temp_config_dir, enable_cache=True)

        # Load initial config
        agent_name = "maven_maintenance_agent"
        initial_config = loader.load_agent(agent_name)
        initial_temperature = initial_config.llm.temperature

        # Modify the YAML file with new temperature
        yaml_path = temp_config_dir / f"{agent_name}.yaml"
        with open(yaml_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        # Change temperature (ensure it's different)
        new_temperature = 0.9 if initial_temperature < 0.5 else 0.1
        config_data["llm"]["temperature"] = new_temperature

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Force reload to pick up changes
        reloaded_config = loader.reload_agent(agent_name)

        # Assert new temperature is applied
        assert reloaded_config.llm.temperature == new_temperature, (
            f"Expected temperature {new_temperature}, " f"got {reloaded_config.llm.temperature}"
        )

        # Assert original temperature was different
        assert (
            initial_temperature != new_temperature
        ), "Test setup error: temperatures should differ"

    def test_yaml_changes_detected_by_cache(self, tmp_path):
        """Test that file modification invalidates cache automatically."""
        # Setup
        real_config_dir = Path("config/agents")
        temp_config_dir = tmp_path / "agents"
        temp_config_dir.mkdir(parents=True)

        for yaml_file in real_config_dir.glob("*.yaml"):
            shutil.copy(yaml_file, temp_config_dir / yaml_file.name)

        loader = AgentLoader(config_dir=temp_config_dir, enable_cache=True)

        # First load - cache the config
        agent_name = "maven_maintenance_agent"
        _ = loader.load_agent(agent_name)  # Initial load to populate cache

        # Modify file and wait (mtime must change)
        yaml_path = temp_config_dir / f"{agent_name}.yaml"
        with open(yaml_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        _ = config_data["llm"]["temperature"]  # Note original value
        config_data["llm"]["temperature"] = 1.5

        # Write with updated timestamp
        import time

        time.sleep(0.1)  # Ensure mtime changes
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Second load - should detect file change and reload
        config2 = loader.load_agent(agent_name)

        assert config2.llm.temperature == 1.5, "Cache should detect file modification and reload"


class TestInvalidYAMLHandling:
    """Test error handling for invalid YAML configurations (T081)."""

    def test_invalid_yaml_fails_startup(self, tmp_path):
        """Test that invalid YAML syntax causes startup failure (T081).

        Introduce YAML syntax error, assert startup raises error,
        assert error message contains line information.
        """
        # Create temp config directory
        temp_config_dir = tmp_path / "agents"
        temp_config_dir.mkdir(parents=True)

        # Create invalid YAML file with syntax error
        invalid_yaml_content = """
name: test_agent
description: Test agent
identity:
  role: Test Role
  persona: Test Persona
llm:
  provider: anthropic
  model: claude-sonnet-4-5-20250929
  temperature: [invalid  # Syntax error - unclosed bracket
tools:
  mcp_servers: []
prompts:
  system: test.md
workflow:
  graph_name: test
  node_name: test
error_handling:
  max_retries: 3
  timeout_seconds: 120
"""
        yaml_path = temp_config_dir / "test_agent.yaml"
        yaml_path.write_text(invalid_yaml_content)

        loader = AgentLoader(config_dir=temp_config_dir)

        # Should raise error when loading invalid YAML
        with pytest.raises(yaml.YAMLError) as exc_info:
            loader.load_agent("test_agent")

        # Error should contain position/line information
        error_message = str(exc_info.value)
        # YAML errors typically contain line or position info
        assert (
            "line" in error_message.lower()
            or "position" in error_message.lower()
            or exc_info.value.problem_mark is not None
        ), f"Error should contain line information: {error_message}"

    def test_missing_required_field_raises_validation_error(self, tmp_path):
        """Test that missing required field raises ValidationError."""
        temp_config_dir = tmp_path / "agents"
        temp_config_dir.mkdir(parents=True)

        # Create YAML missing 'llm' field (required)
        incomplete_yaml = """
name: incomplete_agent
description: Missing required fields
identity:
  role: Test
  persona: Test
# Missing 'llm' field - required by Pydantic schema
tools:
  mcp_servers: []
prompts:
  system: test.md
workflow:
  graph_name: test
  node_name: test
error_handling:
  max_retries: 3
  timeout_seconds: 120
"""
        yaml_path = temp_config_dir / "incomplete_agent.yaml"
        yaml_path.write_text(incomplete_yaml)

        loader = AgentLoader(config_dir=temp_config_dir)

        # Should raise Pydantic ValidationError
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            loader.load_agent("incomplete_agent")

        # Error should mention the missing field
        error_str = str(exc_info.value)
        assert "llm" in error_str.lower(), f"Error should mention 'llm': {error_str}"


class TestPromptTemplateLoading:
    """Test prompt template loading functionality (T082)."""

    def test_prompt_template_loads(self):
        """Test that dependency_update.md prompt loads correctly (T082).

        Assert dependency_update.md exists and loads,
        assert prompt length > 100 chars,
        assert prompt contains expected keywords (e.g., 'dependency', 'Maven').
        """
        # Check file exists
        prompt_path = Path("config/prompts/maven/dependency_update.md")
        assert prompt_path.exists(), f"Prompt template not found: {prompt_path}"

        # Load the prompt
        loader = AgentLoader(config_dir="config/agents")
        prompt_content = loader.load_prompt("dependency_update", category="maven")

        # Assert prompt is non-empty and has substantial content
        assert (
            len(prompt_content) > 100
        ), f"Prompt too short ({len(prompt_content)} chars), expected > 100"

        # Assert prompt contains expected Maven-related keywords
        prompt_lower = prompt_content.lower()
        assert "dependency" in prompt_lower, "Prompt should contain 'dependency'"
        assert "maven" in prompt_lower, "Prompt should contain 'maven'"

        # Additional keywords that should be present for dependency update prompts
        expected_keywords = ["update", "version", "project"]
        for keyword in expected_keywords:
            assert keyword in prompt_lower, f"Prompt should contain '{keyword}'"

    def test_prompt_hot_reload(self, tmp_path):
        """Test that prompt templates support hot-reload."""
        # Setup temp prompts directory
        prompts_dir = tmp_path / "config" / "prompts" / "maven"
        agents_dir = tmp_path / "config" / "agents"
        prompts_dir.mkdir(parents=True)
        agents_dir.mkdir(parents=True)

        # Create initial prompt
        prompt_path = prompts_dir / "test_prompt.md"
        prompt_path.write_text("Initial prompt content for Maven dependency analysis.")

        loader = AgentLoader(config_dir=agents_dir, enable_cache=True)

        # Load initial prompt
        initial_content = loader.load_prompt("test_prompt", category="maven")
        assert "Initial prompt content" in initial_content

        # Modify prompt file
        import time

        time.sleep(0.1)  # Ensure mtime changes
        prompt_path.write_text("Updated prompt content with new Maven instructions.")

        # Force reload
        reloaded_content = loader.reload_prompt("test_prompt", category="maven")
        assert "Updated prompt content" in reloaded_content

    def test_missing_prompt_raises_error(self):
        """Test that loading non-existent prompt raises FileNotFoundError."""
        loader = AgentLoader(config_dir="config/agents")

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_prompt("nonexistent_prompt", category="maven")

        assert (
            "nonexistent_prompt" in str(exc_info.value).lower()
            or "not found" in str(exc_info.value).lower()
        )


class TestAllAgentsValidation:
    """Test bulk validation of all agent configurations."""

    def test_validate_all_agents(self):
        """Test that all agents in config directory pass validation."""
        loader = AgentLoader(config_dir="config/agents")
        results = loader.validate_all_agents()

        # Should validate at least 3 agents
        assert len(results) >= 3, f"Expected at least 3 agents, found {len(results)}"

        # Check expected agents are present
        expected_agents = ["maven_maintenance_agent", "test_gen_agent", "deployment_agent"]
        for agent_name in expected_agents:
            assert agent_name in results, f"Missing validation for {agent_name}"
            is_valid, errors = results[agent_name]
            assert is_valid, f"{agent_name} validation failed: {errors}"
