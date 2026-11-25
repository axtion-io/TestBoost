# SPDX-License-Identifier: Apache-2.0
"""Shared prompt template utilities.

Centralises the load + render pattern used across test_generator and maven tools.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt_template(relative_path: str) -> str:
    """Load a prompt template from src/prompts/<relative_path> (cached).

    The prompts live inside the package so a pip-installed TestBoost
    (e.g. the GitLab CI template) finds them without a repo checkout.

    Args:
        relative_path: Path relative to src/prompts/, e.g. "testing/unit_test_generation.md"

    Returns:
        Template content as string.
    """
    return (_PROMPTS_DIR / relative_path).read_text(encoding="utf-8")


def render_template(template: str, **kwargs: object) -> str:
    """Replace {{key}} placeholders in template with provided values."""
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value) if value is not None else "")
    return template


# First fenced block, whatever its language tag (```java, ```python, ```json, ```).
_CODE_FENCE = re.compile(r"```[\w+#-]*[ \t]*\n(.*?)```", re.DOTALL)


def response_text(response: Any) -> str:
    """Text of a LangChain chat response.

    `content` is a str for plain answers but a list of content blocks for
    some providers/modes (e.g. Anthropic with thinking) — str() of that list
    would feed a Python repr to the compiler.
    """
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def extract_code_block(text: str) -> str:
    """Return the body of the first fenced block, or the whole text if unfenced."""
    match = _CODE_FENCE.search(text)
    return (match.group(1) if match else text).strip()


# JUnit 5 test-method annotations, then pytest functions.
_TEST_METHOD = re.compile(r"@(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b|^\s*(?:async\s+)?def test_", re.M)


def count_tests(code: str) -> int:
    """Number of test methods in a JUnit 5 or pytest file (parameterized tests count once)."""
    return len(_TEST_METHOD.findall(code))


__all__ = ["count_tests", "extract_code_block", "load_prompt_template", "render_template", "response_text"]
