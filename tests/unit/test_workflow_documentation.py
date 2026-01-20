"""Tests to verify workflow documentation matches implementation.

These tests detect drift between docs/workflow-diagrams.md and the actual
implementation in src/core/session.py.
"""

import re
from pathlib import Path

import pytest

from src.core.session import WORKFLOW_STEPS
from src.db.models.session import SessionStatus, SessionType


class TestWorkflowDocumentationSync:
    """Verify documentation stays in sync with implementation."""

    @pytest.fixture
    def workflow_diagrams_content(self) -> str:
        """Load workflow diagrams documentation."""
        docs_path = Path(__file__).parent.parent.parent / "docs" / "workflow-diagrams.md"
        if not docs_path.exists():
            pytest.skip("docs/workflow-diagrams.md not found")
        return docs_path.read_text(encoding="utf-8")

    def test_workflow_types_documented(self, workflow_diagrams_content: str):
        """Verify all WORKFLOW_STEPS keys have corresponding documentation sections."""
        for workflow_type in WORKFLOW_STEPS.keys():
            # Convert snake_case to Title Case for section matching
            # maven_maintenance -> Maven Maintenance
            title = workflow_type.replace("_", " ").title()
            assert (
                f"## {title} Workflow" in workflow_diagrams_content
                or f"## {title.replace(' ', '')} Workflow" in workflow_diagrams_content
            ), f"Workflow '{workflow_type}' not documented in workflow-diagrams.md"

    def test_maven_maintenance_has_five_steps(self):
        """Verify Maven Maintenance workflow has expected 5 steps."""
        steps = WORKFLOW_STEPS.get("maven_maintenance", [])
        assert len(steps) == 5, f"Expected 5 steps for maven_maintenance, got {len(steps)}"

        expected_codes = [
            "analyze_dependencies",
            "identify_vulnerabilities",
            "plan_updates",
            "apply_updates",
            "validate_changes",
        ]
        actual_codes = [s["code"] for s in steps]
        assert actual_codes == expected_codes, f"Step codes mismatch: {actual_codes}"

    def test_test_generation_has_four_steps(self):
        """Verify Test Generation workflow has expected 4 steps."""
        steps = WORKFLOW_STEPS.get("test_generation", [])
        assert len(steps) == 4, f"Expected 4 steps for test_generation, got {len(steps)}"

        expected_codes = [
            "analyze_project",
            "identify_coverage_gaps",
            "generate_tests",
            "validate_tests",
        ]
        actual_codes = [s["code"] for s in steps]
        assert actual_codes == expected_codes, f"Step codes mismatch: {actual_codes}"

    def test_docker_deployment_has_four_steps(self):
        """Verify Docker Deployment workflow has expected 4 steps."""
        steps = WORKFLOW_STEPS.get("docker_deployment", [])
        assert len(steps) == 4, f"Expected 4 steps for docker_deployment, got {len(steps)}"

        expected_codes = [
            "analyze_dockerfile",
            "optimize_image",
            "generate_compose",
            "validate_deployment",
        ]
        actual_codes = [s["code"] for s in steps]
        assert actual_codes == expected_codes, f"Step codes mismatch: {actual_codes}"

    def test_session_status_values_documented(self, workflow_diagrams_content: str):
        """Verify SessionStatus enum values appear in documentation."""
        # These are the key states that should be mentioned
        key_states = ["Pending", "Completed", "Failed"]

        for state in key_states:
            assert state in workflow_diagrams_content, (
                f"SessionStatus '{state}' not found in workflow-diagrams.md"
            )

    def test_session_types_match_workflow_steps(self):
        """Verify SessionType enum matches WORKFLOW_STEPS keys."""
        session_types = {st.value for st in SessionType}
        workflow_types = set(WORKFLOW_STEPS.keys())

        assert session_types == workflow_types, (
            f"SessionType values {session_types} don't match "
            f"WORKFLOW_STEPS keys {workflow_types}"
        )

    def test_step_definitions_have_required_fields(self):
        """Verify all step definitions have code, name, and description."""
        required_fields = {"code", "name", "description"}

        for workflow_type, steps in WORKFLOW_STEPS.items():
            for i, step in enumerate(steps):
                step_keys = set(step.keys())
                missing = required_fields - step_keys
                assert not missing, (
                    f"Step {i} in '{workflow_type}' missing fields: {missing}"
                )

    def test_documentation_mentions_retry_constants(self, workflow_diagrams_content: str):
        """Verify retry constants are documented."""
        assert "MAX_CORRECTION_RETRIES" in workflow_diagrams_content, (
            "MAX_CORRECTION_RETRIES not documented"
        )
        assert "MAX_TEST_ITERATIONS" in workflow_diagrams_content, (
            "MAX_TEST_ITERATIONS not documented"
        )

    def test_documentation_mentions_modification_status(self, workflow_diagrams_content: str):
        """Verify ModificationStatus rollback handling is documented."""
        assert "ModificationStatus" in workflow_diagrams_content, (
            "ModificationStatus not documented in rollback section"
        )
        assert "rolled_back" in workflow_diagrams_content.lower(), (
            "rolled_back status not documented"
        )

    def test_mermaid_diagrams_present(self, workflow_diagrams_content: str):
        """Verify Mermaid diagrams exist for each workflow."""
        mermaid_blocks = re.findall(r"```mermaid\n(.*?)```", workflow_diagrams_content, re.DOTALL)

        # Should have at least: 3 workflow diagrams + rollback + auto-correction + lifecycle
        assert len(mermaid_blocks) >= 5, (
            f"Expected at least 5 Mermaid diagrams, found {len(mermaid_blocks)}"
        )


class TestWorkflowStepNaming:
    """Verify step naming conventions."""

    def test_step_codes_are_snake_case(self):
        """Verify all step codes use snake_case."""
        snake_case_pattern = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

        for workflow_type, steps in WORKFLOW_STEPS.items():
            for step in steps:
                code = step["code"]
                assert snake_case_pattern.match(code), (
                    f"Step code '{code}' in '{workflow_type}' is not snake_case"
                )

    def test_step_names_are_title_case(self):
        """Verify all step names use Title Case."""
        for workflow_type, steps in WORKFLOW_STEPS.items():
            for step in steps:
                name = step["name"]
                # Each word should start with uppercase
                words = name.split()
                for word in words:
                    assert word[0].isupper(), (
                        f"Step name '{name}' in '{workflow_type}' is not Title Case"
                    )
