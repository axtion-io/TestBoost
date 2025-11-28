"""DeepAgents YAML configuration loader."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from src.lib.logging import get_logger

logger = get_logger(__name__)


class ToolConfig(BaseModel):
    """Configuration for an MCP tool."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Configuration for a DeepAgents agent."""

    name: str
    description: str
    system_prompt: str = Field(alias="system-prompt")
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    tools: list[ToolConfig] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list, alias="mcp-servers")
    retry_config: dict[str, Any] = Field(default_factory=dict, alias="retry-config")

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


class WorkflowConfig(BaseModel):
    """Configuration for a complete workflow."""

    name: str
    description: str
    nodes: list[WorkflowNodeConfig]
    agents: dict[str, AgentConfig]


class AgentLoader:
    """Load and validate DeepAgents YAML configurations."""

    def __init__(self, config_dir: str | Path):
        """Initialize loader with configuration directory.

        Args:
            config_dir: Path to directory containing agent YAML files
        """
        self.config_dir = Path(config_dir)

    def load_agent(self, name: str) -> AgentConfig:
        """Load a single agent configuration.

        Args:
            name: Agent name (without .yaml extension)

        Returns:
            Validated AgentConfig

        Raises:
            FileNotFoundError: If agent file not found
            ValidationError: If configuration is invalid
        """
        file_path = self.config_dir / f"{name}.yaml"

        if not file_path.exists():
            raise FileNotFoundError(f"Agent configuration not found: {file_path}")

        logger.info("loading_agent", name=name, path=str(file_path))

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        try:
            config = AgentConfig(**data)
            logger.info("agent_loaded", name=config.name)
            return config
        except ValidationError as e:
            logger.error("agent_validation_error", name=name, error=str(e))
            raise

    def load_workflow(self, name: str) -> WorkflowConfig:
        """Load a workflow configuration with all its agents.

        Args:
            name: Workflow name (without .yaml extension)

        Returns:
            Validated WorkflowConfig with embedded agents

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
            config = WorkflowConfig(
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

    def load_prompt(self, name: str, category: str = "common") -> str:
        """Load a prompt template.

        Args:
            name: Prompt name (without .md extension)
            category: Prompt category subdirectory

        Returns:
            Prompt content

        Raises:
            FileNotFoundError: If prompt file not found
        """
        file_path = self.config_dir.parent / "prompts" / category / f"{name}.md"

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt not found: {file_path}")

        logger.info("loading_prompt", name=name, category=category)

        with open(file_path, encoding="utf-8") as f:
            return f.read()


__all__ = [
    "AgentLoader",
    "AgentConfig",
    "ToolConfig",
    "WorkflowConfig",
    "WorkflowNodeConfig",
]
