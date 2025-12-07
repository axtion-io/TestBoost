"""DeepAgents YAML configuration loader with hot-reload support."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from src.lib.logging import get_logger

logger = get_logger(__name__)


class ConfigCache:
    """Cache for loaded configurations with timestamp tracking."""

    def __init__(self) -> None:
        """Initialize empty cache."""
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str, file_path: Path) -> Any | None:
        """Get cached config if file hasn't been modified.

        Args:
            key: Cache key
            file_path: Path to config file

        Returns:
            Cached config or None if stale/missing
        """
        if key not in self._cache:
            return None

        cached_config, cached_mtime = self._cache[key]

        # Check if file was modified
        if not file_path.exists():
            self._cache.pop(key, None)
            return None

        current_mtime = file_path.stat().st_mtime
        if current_mtime > cached_mtime:
            # File was modified, invalidate cache
            self._cache.pop(key, None)
            return None

        logger.debug("config_cache_hit", key=key)
        return cached_config

    def set(self, key: str, config: Any, file_path: Path) -> None:
        """Store config in cache with current file modification time.

        Args:
            key: Cache key
            config: Config to cache
            file_path: Path to config file
        """
        if file_path.exists():
            mtime = file_path.stat().st_mtime
            self._cache[key] = (config, mtime)
            logger.debug("config_cached", key=key)

    def invalidate(self, key: str | None = None) -> None:
        """Invalidate cache entry or entire cache.

        Args:
            key: Specific key to invalidate, or None for all
        """
        if key is None:
            logger.info("config_cache_cleared", entries=len(self._cache))
            self._cache.clear()
        elif key in self._cache:
            self._cache.pop(key)
            logger.info("config_cache_entry_cleared", key=key)


class IdentityConfig(BaseModel):
    """Agent identity configuration."""

    role: str
    persona: str


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str  # google-genai | anthropic | openai
    model: str
    temperature: float = 0.0
    max_tokens: int | None = None


class ToolsConfig(BaseModel):
    """Tools configuration."""

    mcp_servers: list[str] = Field(default_factory=list)


class PromptsConfig(BaseModel):
    """Prompts configuration."""

    system: str  # Path to system prompt markdown file


class WorkflowConfig(BaseModel):
    """Workflow configuration."""

    graph_name: str
    node_name: str


class ErrorHandlingConfig(BaseModel):
    """Error handling configuration."""

    max_retries: int = 3
    timeout_seconds: int = 120


class AgentConfig(BaseModel):
    """Configuration for a DeepAgents agent (spec.md schema)."""

    name: str
    description: str
    identity: IdentityConfig
    llm: LLMConfig
    tools: ToolsConfig
    prompts: PromptsConfig
    workflow: WorkflowConfig
    error_handling: ErrorHandlingConfig

    model_config = {"populate_by_name": True}


class WorkflowNodeConfig(BaseModel):
    """Configuration for a workflow node."""

    name: str
    agent: str
    next_nodes: list[str] = Field(default_factory=list, alias="next-nodes")
    conditions: dict[str, str] = Field(default_factory=dict)
    is_entry: bool = Field(default=False, alias="is-entry")
    is_terminal: bool = Field(default=False, alias="is-terminal")

    model_config = {"populate_by_name": True}


class WorkflowGraphConfig(BaseModel):
    """Configuration for a complete workflow graph."""

    name: str
    description: str
    nodes: list[WorkflowNodeConfig]
    agents: dict[str, AgentConfig]


class AgentLoader:
    """Load and validate DeepAgents YAML configurations with hot-reload support."""

    def __init__(self, config_dir: str | Path, enable_cache: bool = True) -> None:
        """Initialize loader with configuration directory.

        Args:
            config_dir: Path to directory containing agent YAML files
            enable_cache: Enable config caching with hot-reload (default: True)
        """
        self.config_dir = Path(config_dir)
        self.enable_cache = enable_cache
        self._cache: ConfigCache | None = ConfigCache() if enable_cache else None

    def load_agent(self, name: str, force_reload: bool = False) -> AgentConfig:
        """Load a single agent configuration with hot-reload support.

        Args:
            name: Agent name (without .yaml extension)
            force_reload: Force reload even if cached (default: False)

        Returns:
            Validated AgentConfig

        Raises:
            FileNotFoundError: If agent file not found
            ValidationError: If configuration is invalid
        """
        file_path = self.config_dir / f"{name}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Agent configuration not found: {file_path}")

        # Check cache first (unless force_reload)
        cache_key = f"agent:{name}"
        if self._cache and not force_reload:
            cached = self._cache.get(cache_key, file_path)
            if cached:
                logger.debug("agent_loaded_from_cache", name=name)
                return cached  # type: ignore[return-value]

        logger.info("loading_agent", name=name, path=str(file_path), force_reload=force_reload)

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        try:
            config = AgentConfig(**data)
            logger.info("agent_loaded", name=config.name)

            # Cache the config
            if self._cache:
                self._cache.set(cache_key, config, file_path)

            return config
        except ValidationError as e:
            logger.error("agent_validation_error", name=name, error=str(e))
            raise

    def load_workflow(self, name: str) -> WorkflowGraphConfig:
        """Load a workflow configuration with all its agents.

        Args:
            name: Workflow name (without .yaml extension)

        Returns:
            Validated WorkflowGraphConfig with embedded agents

        Raises:
            FileNotFoundError: If workflow file not found
            ValidationError: If configuration is invalid
        """
        file_path = self.config_dir / "workflows" / f"{name}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Workflow configuration not found: {file_path}")

        logger.info("loading_workflow", name=name, path=str(file_path))

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Load embedded agents or reference external ones
        agents_data = data.get("agents", {})
        agents: dict[str, AgentConfig] = {}

        for agent_name, agent_data in agents_data.items():
            if isinstance(agent_data, str):
                # Reference to external agent file
                agents[agent_name] = self.load_agent(agent_data)
            else:
                # Inline agent definition
                agents[agent_name] = AgentConfig(**agent_data)

        try:
            config = WorkflowGraphConfig(
                name=data["name"],
                description=data.get("description", ""),
                nodes=[WorkflowNodeConfig(**node) for node in data.get("nodes", [])],
                agents=agents,
            )
            logger.info(
                "workflow_loaded",
                name=config.name,
                nodes_count=len(config.nodes),
                agents_count=len(config.agents),
            )
            return config
        except ValidationError as e:
            logger.error("workflow_validation_error", name=name, error=str(e))
            raise

    def load_prompt(self, name: str, category: str = "common", force_reload: bool = False) -> str:
        """Load a prompt template with hot-reload support.

        Args:
            name: Prompt name (without .md extension)
            category: Prompt category subdirectory
            force_reload: Force reload even if cached (default: False)

        Returns:
            Prompt content

        Raises:
            FileNotFoundError: If prompt file not found
        """
        file_path = self.config_dir.parent / "prompts" / category / f"{name}.md"

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt not found: {file_path}")

        # Check cache first (unless force_reload)
        cache_key = f"prompt:{category}:{name}"
        if self._cache and not force_reload:
            cached = self._cache.get(cache_key, file_path)
            if cached:
                logger.debug("prompt_loaded_from_cache", name=name, category=category)
                return cached  # type: ignore[return-value]

        logger.info("loading_prompt", name=name, category=category, force_reload=force_reload)

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Cache the prompt
        if self._cache:
            self._cache.set(cache_key, content, file_path)

        return content

    def reload_all(self) -> None:
        """Force reload all cached configurations.

        This invalidates the entire cache, forcing next load operations
        to re-read from disk. Useful for applying config changes without restart.
        """
        if self._cache:
            self._cache.invalidate()
            logger.info("config_cache_reloaded")

    def reload_agent(self, name: str) -> AgentConfig:
        """Force reload a specific agent configuration.

        Args:
            name: Agent name to reload

        Returns:
            Freshly loaded AgentConfig
        """
        return self.load_agent(name, force_reload=True)

    def reload_prompt(self, name: str, category: str = "common") -> str:
        """Force reload a specific prompt template.

        Args:
            name: Prompt name to reload
            category: Prompt category

        Returns:
            Freshly loaded prompt content
        """
        return self.load_prompt(name, category, force_reload=True)

    def validate_agent_config(self, name: str) -> tuple[bool, list[str]]:
        """Validate an agent configuration without loading it into cache.

        Args:
            name: Agent name to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []
        file_path = self.config_dir / f"{name}.yaml"

        # Check file exists
        if not file_path.exists():
            errors.append(f"Agent configuration file not found: {file_path}")
            return False, errors

        # Try to load and validate
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Validate with Pydantic
            config = AgentConfig(**data)

            # Additional validation checks
            # 1. Check if referenced MCP servers exist in registry
            from src.mcp_servers.registry import list_available_servers

            available_servers = list_available_servers()
            for server_name in config.tools.mcp_servers:
                if server_name not in available_servers:
                    errors.append(
                        f"MCP server '{server_name}' not found in registry. "
                        f"Available: {', '.join(available_servers)}"
                    )

            # 2. Check if prompt file exists
            prompt_path = self.config_dir.parent / "prompts" / config.prompts.system
            if not prompt_path.exists():
                # Try with different base path (handle both absolute and relative)
                alt_prompt_path = Path(config.prompts.system)
                if not alt_prompt_path.exists():
                    errors.append(f"Prompt file not found: {config.prompts.system}")

            # 3. Validate LLM provider
            valid_providers = ["google-genai", "anthropic", "openai"]
            if config.llm.provider not in valid_providers:
                errors.append(
                    f"Invalid LLM provider '{config.llm.provider}'. "
                    f"Valid providers: {', '.join(valid_providers)}"
                )

            # 4. Validate temperature range
            if not 0.0 <= config.llm.temperature <= 2.0:
                errors.append(f"Temperature must be between 0.0 and 2.0, got {config.llm.temperature}")

            # 5. Validate max_tokens
            if config.llm.max_tokens is not None and config.llm.max_tokens <= 0:
                errors.append(f"max_tokens must be positive, got {config.llm.max_tokens}")

            if errors:
                logger.warning("agent_validation_warnings", name=name, warnings=errors)
                return False, errors

            logger.info("agent_validation_success", name=name)
            return True, []

        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e}")
            logger.error("agent_yaml_error", name=name, error=str(e))
            return False, errors

        except ValidationError as e:
            # Extract Pydantic validation errors
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(f"{field}: {error['msg']}")
            logger.error("agent_validation_failed", name=name, errors=errors)
            return False, errors

        except Exception as e:
            errors.append(f"Unexpected validation error: {e}")
            logger.error("agent_validation_exception", name=name, error=str(e))
            return False, errors

    def validate_all_agents(self) -> dict[str, tuple[bool, list[str]]]:
        """Validate all agent configurations in the config directory.

        Returns:
            Dictionary mapping agent name to (is_valid, error_messages)
        """
        results: dict[str, tuple[bool, list[str]]] = {}

        # Find all YAML files in config directory
        yaml_files = list(self.config_dir.glob("*.yaml"))

        for yaml_file in yaml_files:
            agent_name = yaml_file.stem
            results[agent_name] = self.validate_agent_config(agent_name)

        valid_count = sum(1 for is_valid, _ in results.values() if is_valid)
        total_count = len(results)

        logger.info(
            "agents_validation_complete",
            valid=valid_count,
            total=total_count,
            invalid=total_count - valid_count,
        )

        return results

    def backup_config(self, name: str) -> Path:
        """Create a timestamped backup of an agent configuration.

        Args:
            name: Agent name to backup

        Returns:
            Path to backup file

        Raises:
            FileNotFoundError: If agent config doesn't exist
        """
        file_path = self.config_dir / f"{name}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Agent configuration not found: {file_path}")

        # Create backups directory if it doesn't exist
        backups_dir = self.config_dir / ".backups"
        backups_dir.mkdir(exist_ok=True)

        # Create timestamped backup filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = backups_dir / f"{name}_{timestamp}.yaml"

        # Copy file to backup location
        shutil.copy2(file_path, backup_path)

        logger.info("config_backed_up", name=name, backup=str(backup_path))

        return backup_path

    def list_backups(self, name: str | None = None) -> list[tuple[str, datetime, Path]]:
        """List available configuration backups.

        Args:
            name: Optional agent name to filter backups (None for all)

        Returns:
            List of (agent_name, timestamp, path) tuples sorted by timestamp descending
        """
        backups_dir = self.config_dir / ".backups"

        if not backups_dir.exists():
            return []

        backups: list[tuple[str, datetime, Path]] = []

        # Find all backup files
        for backup_file in backups_dir.glob("*.yaml"):
            # Parse filename: <agent_name>_YYYYMMDD_HHMMSS.yaml
            parts = backup_file.stem.rsplit("_", 2)
            if len(parts) != 3:
                continue

            agent_name, date_str, time_str = parts
            timestamp_str = f"{date_str}_{time_str}"

            # Filter by agent name if specified
            if name and agent_name != name:
                continue

            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                backups.append((agent_name, timestamp, backup_file))
            except ValueError:
                # Skip files with invalid timestamp format
                logger.warning("invalid_backup_filename", filename=backup_file.name)
                continue

        # Sort by timestamp descending (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)

        return backups

    def rollback_config(self, name: str, timestamp: datetime | None = None) -> Path:
        """Rollback agent configuration to a previous backup.

        Args:
            name: Agent name to rollback
            timestamp: Specific backup timestamp (None for latest)

        Returns:
            Path to restored backup

        Raises:
            FileNotFoundError: If no backups found
            ValueError: If specified timestamp not found
        """
        backups = self.list_backups(name)

        if not backups:
            raise FileNotFoundError(f"No backups found for agent: {name}")

        # Find the backup to restore
        backup_to_restore: Path | None = None

        if timestamp is None:
            # Use latest backup
            backup_to_restore = backups[0][2]
            logger.info("rollback_to_latest", name=name, timestamp=backups[0][1])
        else:
            # Find specific timestamp
            for agent_name, backup_time, backup_path in backups:
                if backup_time == timestamp:
                    backup_to_restore = backup_path
                    break

            if not backup_to_restore:
                raise ValueError(
                    f"No backup found for {name} at timestamp {timestamp}. "
                    f"Available: {[t for _, t, _ in backups]}"
                )

        # Create backup of current config before rollback
        current_path = self.config_dir / f"{name}.yaml"
        if current_path.exists():
            self.backup_config(name)

        # Restore the backup
        shutil.copy2(backup_to_restore, current_path)

        # Invalidate cache
        if self._cache:
            self._cache.invalidate(f"agent:{name}")

        logger.info("config_rolled_back", name=name, backup=str(backup_to_restore))

        return backup_to_restore


__all__ = [
    "AgentLoader",
    "AgentConfig",
    "ConfigCache",
    "IdentityConfig",
    "LLMConfig",
    "ToolsConfig",
    "PromptsConfig",
    "WorkflowConfig",
    "ErrorHandlingConfig",
    "WorkflowGraphConfig",
    "WorkflowNodeConfig",
]
