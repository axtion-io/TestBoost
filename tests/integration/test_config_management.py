"""Integration tests for config management features."""

import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.agents.loader import AgentLoader
from src.lib.llm import get_llm


class TestConfigHotReload:
    """Test hot-reload functionality (T084)."""

    def test_cache_returns_same_config_if_not_modified(self, tmp_path):
        """Test that cache returns same config if file hasn't been modified."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load config twice
        loader = AgentLoader(config_dir, enable_cache=True)
        config1 = loader.load_agent("test_agent")
        config2 = loader.load_agent("test_agent")

        # Should be same object from cache
        assert config1 is config2

    def test_cache_reloads_if_file_modified(self, tmp_path):
        """Test that cache reloads config if file was modified."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Original description",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load config
        loader = AgentLoader(config_dir, enable_cache=True)
        config1 = loader.load_agent("test_agent")
        assert config1.description == "Original description"

        # Wait to ensure mtime changes (some filesystems have 1s granularity)
        time.sleep(1.1)

        # Modify config
        test_config["description"] = "Modified description"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load again - should detect modification and reload
        config2 = loader.load_agent("test_agent")
        assert config2.description == "Modified description"

    def test_force_reload_bypasses_cache(self, tmp_path):
        """Test that force_reload parameter bypasses cache."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load config
        loader = AgentLoader(config_dir, enable_cache=True)
        config1 = loader.load_agent("test_agent")

        # Force reload
        config2 = loader.load_agent("test_agent", force_reload=True)

        # Should be different objects (reloaded from disk)
        assert config1 is not config2
        assert config1.name == config2.name

    def test_reload_all_clears_cache(self, tmp_path):
        """Test that reload_all() clears entire cache."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Load config
        loader = AgentLoader(config_dir, enable_cache=True)
        config1 = loader.load_agent("test_agent")

        # Clear cache
        loader.reload_all()

        # Load again - should be fresh from disk
        config2 = loader.load_agent("test_agent")
        assert config1 is not config2

    def test_prompt_hot_reload(self, tmp_path):
        """Test that prompts also support hot-reload (T082)."""
        # Create test prompt
        config_dir = tmp_path / "config"
        prompts_dir = config_dir / "prompts" / "test"
        prompts_dir.mkdir(parents=True)

        prompt_path = prompts_dir / "test_prompt.md"
        with open(prompt_path, "w") as f:
            f.write("Original prompt")

        # Load prompt
        loader = AgentLoader(config_dir / "agents", enable_cache=True)
        prompt1 = loader.load_prompt("test_prompt", category="test")
        assert prompt1 == "Original prompt"

        # Wait for mtime change
        time.sleep(1.1)

        # Modify prompt
        with open(prompt_path, "w") as f:
            f.write("Modified prompt")

        # Load again - should detect modification
        prompt2 = loader.load_prompt("test_prompt", category="test")
        assert prompt2 == "Modified prompt"


class TestConfigValidation:
    """Test config validation features (T085)."""

    def test_validate_valid_config(self, tmp_path):
        """Test validation passes for valid config."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.5,
                "max_tokens": 8192,
            },
            "tools": {"mcp_servers": ["maven-maintenance"]},
            "prompts": {"system": "config/prompts/maven/dependency_update.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Validate
        loader = AgentLoader(config_dir)
        is_valid, errors = loader.validate_agent_config("test_agent")

        # Should pass (warnings for missing prompt file are OK for this test)
        if not is_valid:
            # Filter out missing prompt file error (expected in test environment)
            filtered_errors = [e for e in errors if "Prompt file not found" not in e]
            assert len(filtered_errors) == 0, f"Unexpected errors: {filtered_errors}"

    def test_validate_invalid_provider(self, tmp_path):
        """Test validation fails for invalid LLM provider."""
        # Create test config with invalid provider
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "invalid-provider",
                "model": "some-model",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Validate
        loader = AgentLoader(config_dir)
        is_valid, errors = loader.validate_agent_config("test_agent")

        # Should fail
        assert not is_valid
        assert any("Invalid LLM provider" in e for e in errors)

    def test_validate_invalid_temperature(self, tmp_path):
        """Test validation fails for out-of-range temperature."""
        # Create test config with invalid temperature
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 3.0,  # Invalid: > 2.0
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Validate
        loader = AgentLoader(config_dir)
        is_valid, errors = loader.validate_agent_config("test_agent")

        # Should fail
        assert not is_valid
        assert any("Temperature must be between" in e for e in errors)

    def test_validate_invalid_mcp_server(self, tmp_path):
        """Test validation fails for non-existent MCP server."""
        # Create test config with invalid MCP server
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": ["non-existent-server"]},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Validate
        loader = AgentLoader(config_dir)
        is_valid, errors = loader.validate_agent_config("test_agent")

        # Should fail
        assert not is_valid
        assert any("not found in registry" in e for e in errors)

    def test_validate_all_agents(self, tmp_path):
        """Test validate_all_agents() validates multiple configs."""
        # Create multiple test configs
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        # Valid config
        valid_config = {
            "name": "valid_agent",
            "description": "Valid agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        # Invalid config
        invalid_config = {
            "name": "invalid_agent",
            "description": "Invalid agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "invalid-provider",
                "model": "some-model",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        with open(config_dir / "valid_agent.yaml", "w") as f:
            yaml.dump(valid_config, f)

        with open(config_dir / "invalid_agent.yaml", "w") as f:
            yaml.dump(invalid_config, f)

        # Validate all
        loader = AgentLoader(config_dir)
        results = loader.validate_all_agents()

        # Should have results for both agents
        assert len(results) == 2
        assert "invalid_agent" in results

        # Invalid agent should fail
        is_valid, errors = results["invalid_agent"]
        assert not is_valid
        assert len(errors) > 0


class TestProviderSwitching:
    """Test LLM provider switching via config (T086)."""

    def test_switch_provider_via_config(self):
        """Test that changing provider in config works."""
        # Test switching between different providers
        providers_to_test = [
            ("google-genai", "gemini-2.5-flash-preview-09-2025"),
            ("anthropic", "claude-3-sonnet-20240229"),
            ("openai", "gpt-4"),
        ]

        for provider, model in providers_to_test:
            full_model = f"{provider}/{model}"

            # Mock the provider-specific functions to avoid needing API keys
            with patch("src.lib.llm._get_google_llm") as mock_google, \
                 patch("src.lib.llm._get_anthropic_llm") as mock_anthropic, \
                 patch("src.lib.llm._get_openai_llm") as mock_openai:

                # Configure mocks
                mock_google.return_value = object()
                mock_anthropic.return_value = object()
                mock_openai.return_value = object()

                # Get LLM (should call correct provider function)
                get_llm(model=full_model)

                # Verify correct provider was called
                if provider == "google-genai":
                    mock_google.assert_called_once()
                elif provider == "anthropic":
                    mock_anthropic.assert_called_once()
                elif provider == "openai":
                    mock_openai.assert_called_once()


class TestConfigVersioning:
    """Test config versioning and rollback (T083)."""

    def test_backup_config_creates_backup(self, tmp_path):
        """Test that backup_config() creates a timestamped backup."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Backup
        loader = AgentLoader(config_dir)
        backup_path = loader.backup_config("test_agent")

        # Verify backup exists
        assert backup_path.exists()
        assert backup_path.parent == config_dir / ".backups"
        assert "test_agent_" in backup_path.name

    def test_list_backups(self, tmp_path):
        """Test that list_backups() returns all backups."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        test_config = {
            "name": "test_agent",
            "description": "Test agent",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        # Create multiple backups
        loader = AgentLoader(config_dir)
        loader.backup_config("test_agent")
        time.sleep(1.1)  # Ensure different timestamps
        loader.backup_config("test_agent")

        # List backups
        backups = loader.list_backups("test_agent")

        # Should have 2 backups
        assert len(backups) == 2

        # Should be sorted by timestamp descending
        assert backups[0][1] > backups[1][1]

    def test_rollback_config(self, tmp_path):
        """Test that rollback_config() restores previous version."""
        # Create test config
        config_dir = tmp_path / "agents"
        config_dir.mkdir()

        original_config = {
            "name": "test_agent",
            "description": "Original version",
            "identity": {"role": "Test Role", "persona": "Test Persona"},
            "llm": {
                "provider": "google-genai",
                "model": "gemini-2.5-flash-preview-09-2025",
                "temperature": 0.3,
            },
            "tools": {"mcp_servers": []},
            "prompts": {"system": "config/prompts/common/java_expert.md"},
            "workflow": {"graph_name": "test", "node_name": "test"},
            "error_handling": {"max_retries": 3, "timeout_seconds": 120},
        }

        config_path = config_dir / "test_agent.yaml"
        with open(config_path, "w") as f:
            yaml.dump(original_config, f)

        # Backup original
        loader = AgentLoader(config_dir)
        loader.backup_config("test_agent")

        time.sleep(1.1)

        # Modify config
        modified_config = original_config.copy()
        modified_config["description"] = "Modified version"
        with open(config_path, "w") as f:
            yaml.dump(modified_config, f)

        # Verify modification
        config = loader.load_agent("test_agent")
        assert config.description == "Modified version"

        # Rollback
        loader.rollback_config("test_agent")

        # Verify rollback
        config = loader.load_agent("test_agent", force_reload=True)
        assert config.description == "Original version"
