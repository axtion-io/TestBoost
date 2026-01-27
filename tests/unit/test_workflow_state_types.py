"""
Tests for workflow state types - validates Pydantic model behavior.

These tests verify that MavenMaintenanceState and other workflow states
work correctly as Pydantic models with proper validation, serialization,
and attribute access.
"""

import uuid

import pytest
from pydantic import ValidationError

from src.workflows.state import (
    MavenMaintenanceState,
    GeneratedTestsStateModel,
    WorkflowStateModel,
)


class TestMavenMaintenanceStatePydantic:
    """Tests that validate Pydantic model behavior for MavenMaintenanceState."""

    def test_instantiation_with_kwargs(self) -> None:
        """Pydantic model accepts keyword arguments like a class constructor."""
        session_id = uuid.uuid4()
        state = MavenMaintenanceState(
            session_id=session_id,
            project_path="/test/path",
        )

        # Attribute access should work
        assert state.session_id == session_id
        assert state.project_path == "/test/path"

    def test_attribute_access(self) -> None:
        """Pydantic model supports attribute access (not just dict-style)."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # Direct attribute access
        assert state.project_path == "/test/path"
        assert state.current_step == "start"  # Default value
        assert state.completed is False  # Default value

    def test_default_values(self) -> None:
        """Pydantic model should have sensible defaults for all fields."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # Check default values
        assert state.applied_updates == []
        assert state.failed_updates == []
        assert state.pending_updates == []
        assert state.errors == []
        assert state.warnings == []
        assert state.completed is False
        assert state.user_approved is False
        assert state.user_selections == []
        assert state.validation_test_results is None
        assert state.maintenance_branch is None

    def test_mutable_default_handling(self) -> None:
        """Pydantic handles mutable defaults correctly (no shared state)."""
        state1 = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/path1",
        )
        state2 = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/path2",
        )

        # Modifying one should not affect the other
        state1.errors.append("error1")

        assert state1.errors == ["error1"]
        assert state2.errors == []  # Should be empty

    def test_type_validation(self) -> None:
        """Pydantic model should validate types."""
        with pytest.raises(ValidationError):
            # session_id should be UUID, not string
            MavenMaintenanceState(
                session_id="not-a-uuid",  # type: ignore[arg-type]
                project_path="/test/path",
            )

    def test_serialization_to_dict(self) -> None:
        """Pydantic model should serialize to dict with model_dump()."""
        session_id = uuid.uuid4()
        state = MavenMaintenanceState(
            session_id=session_id,
            project_path="/test/path",
        )

        data = state.model_dump()

        assert isinstance(data, dict)
        assert data["session_id"] == session_id
        assert data["project_path"] == "/test/path"
        assert "errors" in data
        assert "applied_updates" in data

    def test_json_serialization(self) -> None:
        """Pydantic model should serialize to JSON."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        json_str = state.model_dump_json()

        assert isinstance(json_str, str)
        assert "/test/path" in json_str


class TestApiRouterCompatibility:
    """Tests simulating how testboost.py uses the state."""

    def test_session_storage_and_retrieval(self) -> None:
        """Test that state can be stored in dict and retrieved."""
        sessions: dict[str, MavenMaintenanceState] = {}

        session_id = str(uuid.uuid4())
        state = MavenMaintenanceState(
            session_id=uuid.UUID(session_id),
            project_path="/test/path",
        )

        sessions[session_id] = state

        # Retrieve and access
        retrieved = sessions[session_id]
        assert retrieved.project_path == "/test/path"
        assert retrieved.session_id == uuid.UUID(session_id)

    def test_state_update_workflow(self) -> None:
        """Test updating state during workflow execution."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # Simulate workflow updates (as done in testboost.py)
        state.current_step = "analyze_maven"
        state.applied_updates.append({"groupId": "test", "artifactId": "lib"})
        state.completed = True

        assert state.current_step == "analyze_maven"
        assert len(state.applied_updates) == 1
        assert state.completed is True

    def test_error_handling_append(self) -> None:
        """Test appending errors (as done in testboost.py)."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # testboost.py does: _sessions[session_id].errors.append(str(e))
        state.errors.append("Test error")

        assert len(state.errors) == 1
        assert state.errors[0] == "Test error"

    def test_user_selections_assignment(self) -> None:
        """Test assigning user_selections (as done in testboost.py)."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # testboost.py does: initial_state.user_selections = request.selected_updates
        state.user_selections = ["org.example:lib1", "org.example:lib2"]

        assert state.user_selections == ["org.example:lib1", "org.example:lib2"]

    def test_validation_test_results(self) -> None:
        """Test validation_test_results field usage."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # Initially None
        assert state.validation_test_results is None

        # Assign results
        state.validation_test_results = {
            "tests_run": 50,
            "tests_passed": 48,
            "tests_failed": 2,
        }

        assert state.validation_test_results["tests_run"] == 50


class TestTestGenerationState:
    """Tests for GeneratedTestsStateModel."""

    def test_instantiation(self) -> None:
        """Test GeneratedTestsStateModel instantiation."""
        state = GeneratedTestsStateModel(
            session_id=uuid.uuid4(),
            project_path="/test/path",
            target_mutation_score=85.0,
        )

        assert state.target_mutation_score == 85.0
        assert state.generated_unit_tests == []
        assert state.mutation_score == 0.0

    def test_generated_tests_tracking(self) -> None:
        """Test tracking generated tests."""
        state = GeneratedTestsStateModel(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        state.generated_unit_tests.append({"class": "TestFoo", "methods": ["testBar"]})
        state.generated_integration_tests.append(
            {"class": "TestFooIT", "methods": ["testIntegration"]}
        )
        state.mutation_score = 82.5

        assert len(state.generated_unit_tests) == 1
        assert len(state.generated_integration_tests) == 1
        assert state.mutation_score == 82.5


class TestWorkflowStateModel:
    """Tests for base WorkflowStateModel."""

    def test_extra_fields_allowed(self) -> None:
        """Test that extra fields are allowed (for flexibility)."""
        state = WorkflowStateModel(
            session_id=uuid.uuid4(),
            project_path="/test/path",
            custom_field="custom_value",  # type: ignore[call-arg]
        )

        # Extra fields should be accessible
        assert state.model_extra.get("custom_field") == "custom_value"

    def test_mode_defaults(self) -> None:
        """Test mode defaults to interactive."""
        state = WorkflowStateModel(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        assert state.mode == "interactive"


class TestDictLikeAccess:
    """Tests for dict-like access methods on Pydantic models."""

    def test_get_method(self) -> None:
        """Test dict-like get() method."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # Get existing field
        assert state.get("project_path") == "/test/path"
        # Get with default for missing
        assert state.get("nonexistent", "default") == "default"
        assert state.get("nonexistent") is None

    def test_getitem(self) -> None:
        """Test dict-like [] access."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        assert state["project_path"] == "/test/path"
        assert state["current_step"] == "start"

        with pytest.raises(KeyError):
            _ = state["nonexistent"]

    def test_setitem(self) -> None:
        """Test dict-like [] assignment."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        state["current_step"] = "analyze"
        assert state.current_step == "analyze"

    def test_contains(self) -> None:
        """Test 'in' operator."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        assert "project_path" in state
        assert "current_step" in state
        assert "nonexistent" not in state

    def test_keys_and_items(self) -> None:
        """Test keys() and items() methods."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        keys = state.keys()
        assert "session_id" in keys
        assert "project_path" in keys
        assert "errors" in keys

        items = state.items()
        assert any(k == "project_path" and v == "/test/path" for k, v in items)

    def test_dict_unpacking(self) -> None:
        """Test **state dict unpacking."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        # Create new dict with unpacked state
        data = {**state}  # type: ignore[misc]

        assert data["project_path"] == "/test/path"

    def test_update_method(self) -> None:
        """Test update() method from dict."""
        state = MavenMaintenanceState(
            session_id=uuid.uuid4(),
            project_path="/test/path",
        )

        state.update({"current_step": "updated", "completed": True})

        assert state.current_step == "updated"
        assert state.completed is True
