# SPDX-License-Identifier: Apache-2.0
"""Plugin registry — central catalog of all available technology plugins."""

from pathlib import Path

from src.lib.plugins.base import TechnologyPlugin


class PluginRegistry:
    """Central catalog of all available TestBoost technology plugins.

    Plugins are tried in registration order during auto-detection.
    The first plugin whose detection_patterns match the project root wins.
    """

    def __init__(self) -> None:
        self._plugins: list[TechnologyPlugin] = []

    def register(self, plugin: TechnologyPlugin) -> None:
        """Add a plugin to the registry.

        ABC enforcement already happened at instantiation time — Python raises
        TypeError if any abstract member is missing before this method is even called.

        Args:
            plugin: An instantiated TechnologyPlugin implementation.
        """
        self._plugins.append(plugin)

    def detect(self, project_path: Path) -> TechnologyPlugin | None:
        """Return the first plugin whose detection patterns match project_path.

        Iterates plugins in registration order (first registered = highest priority).
        Returns None if no plugin matches.

        Args:
            project_path: Project root directory to check.

        Returns:
            Matching TechnologyPlugin, or None if no match found.
        """
        project_path = Path(project_path)
        for plugin in self._plugins:
            for pattern in plugin.detection_patterns:
                if (project_path / pattern).exists():
                    return plugin
        return None

    def get(self, identifier: str) -> TechnologyPlugin:
        """Return plugin by identifier.

        Args:
            identifier: Technology identifier (e.g. 'java-spring').

        Returns:
            Matching TechnologyPlugin.

        Raises:
            ValueError: If identifier not found. Message includes available IDs.
        """
        for plugin in self._plugins:
            if plugin.identifier == identifier:
                return plugin
        available = [p.identifier for p in self._plugins]
        raise ValueError(
            f"Plugin '{identifier}' not found. Available: {available}"
        )

    def list_plugins(self) -> list[dict]:
        """Return info dicts for all registered plugins.

        Returns:
            List of dicts with identifier, description, detection_patterns.
        """
        return [
            {
                "identifier": p.identifier,
                "description": p.description,
                "detection_patterns": p.detection_patterns,
            }
            for p in self._plugins
        ]
