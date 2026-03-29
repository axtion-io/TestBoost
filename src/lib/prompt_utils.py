# SPDX-License-Identifier: Apache-2.0
"""Shared prompt template utilities.

Centralises the load + render pattern used across test_generator and maven tools.
"""

from functools import lru_cache
from pathlib import Path

_TESTBOOST_ROOT = Path(__file__).parent.parent.parent


@lru_cache(maxsize=32)
def load_prompt_template(relative_path: str) -> str:
    """Load a prompt template from config/prompts/<relative_path> (cached).

    Args:
        relative_path: Path relative to config/prompts/, e.g. "testing/unit_test_generation.md"

    Returns:
        Template content as string.
    """
    return (_TESTBOOST_ROOT / "config" / "prompts" / relative_path).read_text(encoding="utf-8")


def render_template(template: str, **kwargs: object) -> str:
    """Replace {{key}} placeholders in template with provided values."""
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value) if value is not None else "")
    return template


__all__ = ["load_prompt_template", "render_template"]
