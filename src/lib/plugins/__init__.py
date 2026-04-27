# SPDX-License-Identifier: Apache-2.0
"""TestBoost technology plugin system.

Plugins are registered here in detection-priority order.
First plugin whose detection_patterns match a project root wins.

To add a new plugin:
1. Create src/lib/plugins/<your_plugin>.py implementing TechnologyPlugin
2. Add _registry.register(YourPlugin()) below
3. No other files need to change.
"""

from src.lib.plugins.base import TechnologyPlugin
from src.lib.plugins.go_testing_stub import GoTestingPlugin
from src.lib.plugins.java_spring import JavaSpringPlugin
from src.lib.plugins.python_pytest import PythonPytestPlugin
from src.lib.plugins.registry import PluginRegistry

_registry = PluginRegistry()
_registry.register(JavaSpringPlugin())    # priority 1 — checked first
_registry.register(PythonPytestPlugin())  # priority 2
_registry.register(GoTestingPlugin())     # priority 3 (stub — demonstrates extensibility)


def get_registry() -> PluginRegistry:
    """Return the global plugin registry."""
    return _registry


__all__ = ["TechnologyPlugin", "PluginRegistry", "get_registry"]
