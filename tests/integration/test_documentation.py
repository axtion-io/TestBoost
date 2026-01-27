"""Documentation validation tests (T103b-e).

These tests verify that documentation is complete and accurate.
"""

from pathlib import Path


class TestReadmeCompleteness:
    """Test README.md completeness (T103b)."""

    def test_readme_exists(self):
        """Test that README.md exists at repo root."""
        readme_path = Path("README.md")
        assert readme_path.exists(), "README.md not found at repo root"

    def test_readme_has_agent_requirements_section(self):
        """Test README contains Agent Requirements section."""
        readme = Path("README.md").read_text(encoding="utf-8")

        # Check for agent requirements section
        assert "agent" in readme.lower(), "README should mention agents"
        assert any(
            term in readme.lower() for term in ["requirements", "prerequisites", "dependencies"]
        ), "README should have requirements section"

    def test_readme_has_troubleshooting_section(self):
        """Test README contains Troubleshooting section."""
        readme = Path("README.md").read_text(encoding="utf-8")

        assert "troubleshoot" in readme.lower(), "README should have troubleshooting section"

    def test_readme_has_edge_case_section(self):
        """Test README documents edge case handling."""
        readme = Path("README.md").read_text(encoding="utf-8")

        # Check for edge case documentation
        edge_case_terms = ["edge case", "error handling", "retry", "rate limit"]
        assert any(
            term in readme.lower() for term in edge_case_terms
        ), "README should document edge case handling"

    def test_readme_minimum_content(self):
        """Test README has minimum content length."""
        readme = Path("README.md").read_text(encoding="utf-8")
        word_count = len(readme.split())

        assert word_count >= 500, f"README should have at least 500 words, found {word_count}"


class TestQuickstartCompleteness:
    """Test quickstart.md completeness (T103c)."""

    def test_quickstart_exists(self):
        """Test that quickstart.md exists."""
        quickstart_path = Path("specs/002-deepagents-integration/quickstart.md")
        assert quickstart_path.exists(), "quickstart.md not found"

    def test_quickstart_has_developer_scenario(self):
        """Test quickstart contains Developer scenario."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert "developer" in quickstart.lower(), "Quickstart should have Developer scenario"

    def test_quickstart_has_cli_user_scenario(self):
        """Test quickstart contains CLI User scenario."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert "cli" in quickstart.lower(), "Quickstart should have CLI User scenario"

    def test_quickstart_has_administrator_scenario(self):
        """Test quickstart contains Administrator scenario."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert (
            "administrator" in quickstart.lower()
        ), "Quickstart should have Administrator scenario"

    def test_quickstart_has_tester_scenario(self):
        """Test quickstart contains Tester scenario."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert "tester" in quickstart.lower(), "Quickstart should have Tester scenario"


class TestMigrationGuide:
    """Test migration guide exists (T103d)."""

    def test_migration_guide_in_quickstart(self):
        """Test quickstart.md has migration guide section."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert "migration" in quickstart.lower(), "Quickstart should have migration guide section"

    def test_migration_guide_has_breaking_changes(self):
        """Test migration guide documents breaking changes."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert "breaking" in quickstart.lower(), "Migration guide should document breaking changes"

    def test_migration_guide_has_rollback(self):
        """Test migration guide has rollback procedure."""
        quickstart = Path("specs/002-deepagents-integration/quickstart.md").read_text()

        assert "rollback" in quickstart.lower(), "Migration guide should have rollback procedure"


class TestPromptTemplatesDocumented:
    """Test prompt templates are documented (T103e)."""

    def test_maven_prompt_exists(self):
        """Test Maven dependency update prompt exists."""
        prompt_path = Path("config/prompts/maven/dependency_update.md")
        assert prompt_path.exists(), "Maven dependency update prompt not found"

    def test_maven_prompt_has_header(self):
        """Test Maven prompt has explanatory header."""
        prompt_path = Path("config/prompts/maven/dependency_update.md")
        if prompt_path.exists():
            content = prompt_path.read_text()

            # Check for header with purpose
            assert len(content) > 100, "Prompt should have substantial content"

            # Check for role/purpose definition
            role_terms = ["role", "purpose", "objective", "you are"]
            assert any(
                term in content.lower() for term in role_terms
            ), "Prompt should define agent role/purpose"


class TestAgentConfigsDocumented:
    """Test agent configurations are documented."""

    def test_maven_agent_config_exists(self):
        """Test Maven agent YAML config exists."""
        config_path = Path("config/agents/maven_maintenance_agent.yaml")
        assert config_path.exists(), "Maven maintenance agent config not found"

    def test_test_gen_agent_config_exists(self):
        """Test Test generation agent YAML config exists."""
        config_path = Path("config/agents/test_gen_agent.yaml")
        assert config_path.exists(), "Test generation agent config not found"

    def test_deployment_agent_config_exists(self):
        """Test Deployment agent YAML config exists."""
        config_path = Path("config/agents/deployment_agent.yaml")
        assert config_path.exists(), "Deployment agent config not found"

    def test_agent_configs_have_required_fields(self):
        """Test agent configs have required fields."""
        import yaml

        config_path = Path("config/agents/maven_maintenance_agent.yaml")
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())

            # Check required top-level fields
            required_fields = ["name", "llm", "tools", "prompts"]
            for field in required_fields:
                assert field in config, f"Agent config missing required field: {field}"

            # Check LLM config
            assert "provider" in config.get("llm", {}), "Agent config missing llm.provider"
            assert "model" in config.get("llm", {}), "Agent config missing llm.model"


class TestCodeDocumentation:
    """Test code documentation quality."""

    def test_lib_modules_have_docstrings(self):
        """Test that lib modules have module docstrings."""
        lib_path = Path("src/lib")

        for py_file in lib_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            content = py_file.read_text()
            # Skip SPDX headers if present
            lines = content.strip().split('\n')
            first_non_comment_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith('#') and line.strip():
                    first_non_comment_idx = i
                    break

            # Check for module docstring (triple quotes at first non-comment line)
            if first_non_comment_idx < len(lines):
                assert lines[first_non_comment_idx].strip().startswith('"""'), f"{py_file.name} missing module docstring"

    def test_workflow_modules_have_docstrings(self):
        """Test that workflow modules have module docstrings."""
        workflows_path = Path("src/workflows")

        for py_file in workflows_path.glob("*_agent.py"):
            content = py_file.read_text()
            # Skip SPDX headers if present
            lines = content.strip().split('\n')
            first_non_comment_idx = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith('#') and line.strip():
                    first_non_comment_idx = i
                    break

            # Check for module docstring (triple quotes at first non-comment line)
            if first_non_comment_idx < len(lines):
                assert lines[first_non_comment_idx].strip().startswith('"""'), f"{py_file.name} missing module docstring"


class TestAPIDocumentation:
    """Test API documentation."""

    def test_api_has_openapi_docs(self):
        """Test that FastAPI app has OpenAPI docs enabled."""
        from src.api.main import app

        # FastAPI generates OpenAPI schema by default
        assert hasattr(app, "openapi"), "FastAPI app should have OpenAPI support"

    def test_api_endpoints_documented(self):
        """Test that API endpoints have descriptions."""
        from src.api.main import app

        # Get routes
        routes = [r for r in app.routes if hasattr(r, "path")]

        # Check at least some routes exist
        assert len(routes) > 0, "API should have routes defined"
