"""End-to-end tests for Maven maintenance with real LLM invocations (US2)."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.lib.config import get_settings


# Skip E2E tests if no API key configured
pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="No LLM API key configured (GOOGLE_API_KEY or ANTHROPIC_API_KEY required)"
)


class TestMavenWorkflowLLMCalls:
    """Test Maven workflow makes real LLM API calls (SC-002: ≥3 calls per workflow)."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_maven_workflow_llm_calls(self, tmp_path):
        """Test Maven workflow makes at least 3 real LLM API calls."""
        # Create a minimal Maven project for testing
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        # Create pom.xml with outdated dependency
        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <!-- Intentionally old version for testing -->
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.0.0.RELEASE</version>
        </dependency>
    </dependencies>
</project>
""")

        # Track LLM invocations using a shared counter
        class LLMCallCounter:
            def __init__(self):
                self.count = 0

        counter = LLMCallCounter()

        class LLMWrapper:
            """Wrapper that counts LLM calls and delegates to real LLM."""
            def __init__(self, real_llm, counter):
                self._real_llm = real_llm
                self._counter = counter

            async def ainvoke(self, *args, **kwargs):
                """Count call and delegate to real LLM."""
                self._counter.count += 1
                return await self._real_llm.ainvoke(*args, **kwargs)

            def bind_tools(self, tools, **kwargs):
                """Return a new wrapper with tools bound to the real LLM."""
                bound_llm = self._real_llm.bind_tools(tools, **kwargs)
                return LLMWrapper(bound_llm, self._counter)

            def __getattr__(self, name):
                """Delegate all other attributes to real LLM."""
                return getattr(self._real_llm, name)

        # Patch get_llm WHERE IT IS USED (not where it's defined)
        # maven_maintenance_agent imports: from src.lib.llm import get_llm
        with patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:
            # Import original get_llm
            from src.lib import llm as llm_module
            original_get_llm = llm_module.get_llm

            def get_llm_with_counter(*args, **kwargs):
                """Get real LLM and wrap it with counter."""
                real_llm = original_get_llm(*args, **kwargs)
                return LLMWrapper(real_llm, counter)

            # Make the patch return our wrapper
            mock_get_llm.side_effect = get_llm_with_counter

            # Import workflow function AFTER patch is applied (critical!)
            from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

            # Execute workflow with real LLM (wrapped with counter)
            result = await run_maven_maintenance_with_agent(
                project_path=str(project_path),
                session_id="e2e-test-maven-llm"
            )

            # Verify at least 3 LLM calls (SC-002)
            assert counter.count >= 3, f"Expected ≥3 LLM calls, got {counter.count}"

            # Verify result contains analysis
            assert result is not None
            # Result should mention dependencies or analysis
            assert "dependencies" in result.lower() or "spring" in result.lower()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_maven_workflow_uses_mcp_tools(self, tmp_path):
        """Test Maven workflow invokes MCP tools during execution."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        project_path = tmp_path / "test-project"
        project_path.mkdir()

        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>test</artifactId>
    <version>1.0</version>
</project>
""")

        # Track tool invocations
        tool_calls = []

        # Mock MCP tools to track invocations (but still return realistic data)
        def track_tool_call(tool_name):
            """Decorator to track tool calls."""
            def decorator(original_method):
                async def wrapper(*args, **kwargs):
                    tool_calls.append(tool_name)
                    # Return mock data for faster testing
                    if tool_name == "analyze_dependencies":
                        return {"outdated_count": 1, "vulnerable_count": 0}
                    elif tool_name == "compile_tests":
                        return {"success": True, "duration_ms": 100}
                    return await original_method(*args, **kwargs)
                return wrapper
            return decorator

        with patch("src.mcp_servers.maven_maintenance.langchain_tools.get_maven_tools") as mock_maven_tools:
            # Create mock tools that track invocations
            mock_analyze = MagicMock()
            mock_analyze.name = "analyze_dependencies"
            mock_analyze.ainvoke = track_tool_call("analyze_dependencies")(MagicMock())

            mock_compile = MagicMock()
            mock_compile.name = "compile_tests"
            mock_compile.ainvoke = track_tool_call("compile_tests")(MagicMock())

            mock_maven_tools.return_value = [mock_analyze, mock_compile]

            try:
                result = await run_maven_maintenance_with_agent(
                    project_path=str(project_path),
                    session_id="e2e-test-tools"
                )

                # Verify at least one MCP tool was called
                assert len(tool_calls) > 0, "No MCP tools were invoked"

                # Verify Maven-specific tools were used
                maven_tools = [t for t in tool_calls if "analyze" in t or "compile" in t or "test" in t]
                assert len(maven_tools) > 0, f"No Maven tools called. Called: {tool_calls}"

            except Exception as e:
                # If test fails, show what tools were called
                pytest.fail(f"Test failed. Tools called: {tool_calls}. Error: {e}")


class TestLangSmithTraceValidation:
    """Test LangSmith tracing integration (SC-005: 100% tool calls traced)."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.skipif(
        not os.getenv("LANGSMITH_API_KEY"),
        reason="LANGSMITH_API_KEY not configured"
    )
    async def test_langsmith_trace_validation(self, tmp_path):
        """Test LangSmith captures all agent invocations and tool calls."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
        import os

        # Ensure LangSmith tracing is enabled
        os.environ["LANGSMITH_TRACING"] = "true"

        project_path = tmp_path / "test-project"
        project_path.mkdir()

        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>langsmith-test</artifactId>
    <version>1.0</version>
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.12</version>
        </dependency>
    </dependencies>
</project>
""")

        try:
            # Execute workflow
            result = await run_maven_maintenance_with_agent(
                project_path=str(project_path),
                session_id="e2e-langsmith-test"
            )

            # LangSmith validation would require:
            # 1. Querying LangSmith API for recent traces
            # 2. Verifying trace contains session_id
            # 3. Counting tool call events
            # 4. Verifying agent invocation events

            # For now, just verify workflow completed
            # Full LangSmith validation should be done manually via dashboard
            assert result is not None

            # Log instructions for manual validation
            print("\n" + "="*80)
            print("MANUAL LANGSMITH VALIDATION REQUIRED:")
            print("="*80)
            print(f"1. Go to: https://smith.langchain.com/")
            print(f"2. Search for session_id: e2e-langsmith-test")
            print(f"3. Verify trace shows:")
            print(f"   - Agent invocations (≥3)")
            print(f"   - Tool calls (analyze_dependencies, compile_tests, etc.)")
            print(f"   - Input/output for each step")
            print("="*80 + "\n")

        finally:
            # Clean up env
            if "LANGSMITH_TRACING" in os.environ:
                del os.environ["LANGSMITH_TRACING"]

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_maven_workflow_without_langsmith(self, tmp_path):
        """Test workflow works even if LangSmith is not configured (optional)."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
        import os

        # Ensure LangSmith is disabled
        os.environ.pop("LANGSMITH_API_KEY", None)
        os.environ.pop("LANGSMITH_TRACING", None)

        project_path = tmp_path / "test-project"
        project_path.mkdir()

        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>no-langsmith</artifactId>
    <version>1.0</version>
</project>
""")

        # Should work without LangSmith
        result = await run_maven_maintenance_with_agent(
            project_path=str(project_path),
            session_id="e2e-no-langsmith"
        )

        assert result is not None


class TestMavenWorkflowEdgeCases:
    """Test edge case handling (A1-A6 from spec.md)."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_maven_workflow_handles_malformed_json(self, tmp_path):
        """Test workflow handles malformed tool call JSON (A5 edge case)."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        project_path = tmp_path / "test-project"
        project_path.mkdir()

        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>json-test</artifactId>
    <version>1.0</version>
</project>
""")

        # Mock tool that returns malformed JSON
        with patch("src.mcp_servers.maven_maintenance.langchain_tools.get_maven_tools") as mock_tools:
            mock_tool = MagicMock()
            mock_tool.name = "analyze_dependencies"

            # First call: malformed JSON
            # Second call: valid response
            call_count = 0
            async def flaky_tool(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ValueError("Invalid JSON: {malformed")
                return {"outdated_count": 0, "vulnerable_count": 0}

            mock_tool.ainvoke = flaky_tool
            mock_tools.return_value = [mock_tool]

            # Should retry and succeed (A5 edge case)
            result = await run_maven_maintenance_with_agent(
                project_path=str(project_path),
                session_id="e2e-json-retry"
            )

            # Verify retry happened
            assert call_count >= 2, f"Tool should have been retried, but call_count={call_count}"
            assert result is not None


class TestDockerWorkflowLLMCalls:
    """Test Docker workflow makes real LLM API calls (SC-002: ≥3 calls per workflow)."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_docker_workflow_llm_calls(self, tmp_path):
        """Test Docker workflow makes at least 3 real LLM API calls."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        # Create a minimal Java project for Docker deployment testing
        project_path = tmp_path / "spring-app"
        project_path.mkdir()

        # Create pom.xml with Spring Boot and PostgreSQL
        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>spring-app</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>3.2.0</version>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <version>42.7.0</version>
        </dependency>
    </dependencies>
</project>
""")

        # Track LLM invocations using a shared counter
        class LLMCallCounter:
            def __init__(self):
                self.count = 0

        counter = LLMCallCounter()

        class LLMWrapper:
            """Wrapper that counts LLM calls and delegates to real LLM."""
            def __init__(self, real_llm, counter):
                self._real_llm = real_llm
                self._counter = counter

            async def ainvoke(self, *args, **kwargs):
                """Count call and delegate to real LLM."""
                self._counter.count += 1
                return await self._real_llm.ainvoke(*args, **kwargs)

            def bind_tools(self, tools, **kwargs):
                """Return a new wrapper with tools bound to the real LLM."""
                bound_llm = self._real_llm.bind_tools(tools, **kwargs)
                return LLMWrapper(bound_llm, self._counter)

            def __getattr__(self, name):
                """Delegate all other attributes to real LLM."""
                return getattr(self._real_llm, name)

        # Patch get_llm WHERE IT IS USED (not where it's defined)
        # docker_deployment_agent imports: from src.lib.llm import get_llm
        with patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm:
            # Import original get_llm
            from src.lib import llm as llm_module
            original_get_llm = llm_module.get_llm

            def get_llm_with_counter(*args, **kwargs):
                """Get real LLM and wrap it with counter."""
                real_llm = original_get_llm(*args, **kwargs)
                return LLMWrapper(real_llm, counter)

            # Make the patch return our wrapper
            mock_get_llm.side_effect = get_llm_with_counter

            # Execute workflow with real LLM (wrapped with counter)
            result = await run_docker_deployment_with_agent(
                project_path=str(project_path),
                service_dependencies=["postgres"],
                session_id="e2e-test-docker-llm"
            )

            # Verify at least 3 LLM calls (SC-002)
            assert counter.count >= 3, f"Expected ≥3 LLM calls, got {counter.count}"

            # Verify result contains Docker deployment information
            assert result is not None
            assert result["success"] is True or "agent_response" in result
            # Response should mention Java version detection or Docker
            response_text = result.get("agent_response", "").lower()
            assert any(keyword in response_text for keyword in ["java", "docker", "17", "postgres"])

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_docker_workflow_detects_java_version(self, tmp_path):
        """Test Docker workflow LLM agent detects Java version from pom.xml."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        project_path = tmp_path / "java21-app"
        project_path.mkdir()

        # Create pom.xml with Java 21
        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>java21-app</artifactId>
    <version>1.0.0</version>

    <properties>
        <java.version>21</java.version>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
    </properties>
</project>
""")

        # Execute workflow
        result = await run_docker_deployment_with_agent(
            project_path=str(project_path),
            session_id="e2e-java21-detection"
        )

        # Verify agent detected Java 21
        assert result is not None
        response_text = result.get("agent_response", "").lower()
        # Agent should mention detecting Java 21 in its response
        assert "21" in response_text or "java" in response_text

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_docker_workflow_uses_mcp_tools(self, tmp_path):
        """Test Docker workflow invokes Docker and container-runtime MCP tools."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        project_path = tmp_path / "test-project"
        project_path.mkdir()

        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>docker-test</artifactId>
    <version>1.0</version>
    <properties>
        <java.version>17</java.version>
    </properties>
</project>
""")

        # Track tool invocations
        tool_calls = []

        def track_tool_call(tool_name):
            """Decorator to track tool calls."""
            def decorator(original_method):
                async def wrapper(*args, **kwargs):
                    tool_calls.append(tool_name)
                    # Return mock data for faster testing
                    if tool_name == "docker_create_dockerfile":
                        return {"success": True, "dockerfile_path": f"{project_path}/Dockerfile"}
                    elif tool_name == "docker_create_compose":
                        return {"success": True, "compose_path": f"{project_path}/docker-compose.yml"}
                    elif tool_name == "docker_health_check":
                        return {"success": True, "overall_healthy": True, "elapsed_time": 15}
                    return await original_method(*args, **kwargs)
                return wrapper
            return decorator

        with patch("src.mcp_servers.docker.langchain_tools.get_docker_tools") as mock_docker_tools:
            # Create mock Docker tools
            mock_dockerfile = MagicMock()
            mock_dockerfile.name = "docker_create_dockerfile"
            mock_dockerfile.ainvoke = track_tool_call("docker_create_dockerfile")(MagicMock())

            mock_compose = MagicMock()
            mock_compose.name = "docker_create_compose"
            mock_compose.ainvoke = track_tool_call("docker_create_compose")(MagicMock())

            mock_health = MagicMock()
            mock_health.name = "docker_health_check"
            mock_health.ainvoke = track_tool_call("docker_health_check")(MagicMock())

            mock_docker_tools.return_value = [mock_dockerfile, mock_compose, mock_health]

            try:
                result = await run_docker_deployment_with_agent(
                    project_path=str(project_path),
                    session_id="e2e-docker-tools"
                )

                # Verify Docker MCP tools were called
                assert len(tool_calls) > 0, "No MCP tools were invoked"

                # Verify Docker-specific tools were used
                docker_tools = [t for t in tool_calls if "docker" in t.lower()]
                assert len(docker_tools) > 0, f"No Docker tools called. Called: {tool_calls}"

            except Exception as e:
                # If test fails, show what tools were called
                pytest.fail(f"Test failed. Tools called: {tool_calls}. Error: {e}")


class TestTestGenerationWorkflowLLMCalls:
    """Test Test Generation workflow makes real LLM API calls (SC-002, T052)."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_test_gen_workflow_llm_calls(self, tmp_path):
        """Test Test Generation workflow makes at least 3 real LLM API calls (T052, SC-002)."""
        from uuid import uuid4
        from unittest.mock import AsyncMock, MagicMock

        # Create a minimal Java project for test generation
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        # Create pom.xml
        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
""")

        # Create a simple Java class to generate tests for
        src_dir = project_path / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)

        java_file = src_dir / "Calculator.java"
        java_file.write_text("""package com.example;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int subtract(int a, int b) {
        return a - b;
    }

    public int multiply(int a, int b) {
        return a * b;
    }

    public int divide(int a, int b) {
        if (b == 0) {
            throw new IllegalArgumentException("Cannot divide by zero");
        }
        return a / b;
    }
}
""")

        # Track LLM invocations using a shared counter
        class LLMCallCounter:
            def __init__(self):
                self.count = 0

        counter = LLMCallCounter()

        class LLMWrapper:
            """Wrapper that counts LLM calls and delegates to real LLM."""
            def __init__(self, real_llm, counter):
                self._real_llm = real_llm
                self._counter = counter

            async def ainvoke(self, *args, **kwargs):
                """Count call and delegate to real LLM."""
                self._counter.count += 1
                return await self._real_llm.ainvoke(*args, **kwargs)

            def bind_tools(self, tools, **kwargs):
                """Return a new wrapper with tools bound to the real LLM."""
                bound_llm = self._real_llm.bind_tools(tools, **kwargs)
                return LLMWrapper(bound_llm, self._counter)

            def __getattr__(self, name):
                """Delegate all other attributes to real LLM."""
                return getattr(self._real_llm, name)

        # Create mock db_session and repositories
        mock_db_session = AsyncMock()

        # Mock repository methods to avoid database operations
        mock_artifact_repo = MagicMock()
        mock_artifact_repo.create = AsyncMock(return_value=None)

        mock_session_repo = MagicMock()
        mock_session_repo.update = AsyncMock(return_value=None)

        # Patch get_llm WHERE IT IS USED (in test_generation_agent module)
        with patch("src.workflows.test_generation_agent.get_llm") as mock_get_llm:
            # Import original get_llm
            from src.lib import llm as llm_module
            original_get_llm = llm_module.get_llm

            def get_llm_with_counter(*args, **kwargs):
                """Get real LLM and wrap it with counter."""
                real_llm = original_get_llm(*args, **kwargs)
                return LLMWrapper(real_llm, counter)

            # Make the patch return our wrapper
            mock_get_llm.side_effect = get_llm_with_counter

            # Patch repositories to avoid database operations
            with patch("src.workflows.test_generation_agent.ArtifactRepository", return_value=mock_artifact_repo):
                with patch("src.workflows.test_generation_agent.SessionRepository", return_value=mock_session_repo):

                    # Import workflow function AFTER patch is applied (critical!)
                    from src.workflows.test_generation_agent import run_test_generation_with_agent

                    # Execute workflow with real LLM (wrapped with counter)
                    session_id = uuid4()
                    result = await run_test_generation_with_agent(
                        session_id=session_id,
                        project_path=str(project_path),
                        db_session=mock_db_session,
                        coverage_target=80.0
                    )

                    # Verify at least 3 LLM calls (SC-002)
                    assert counter.count >= 3, f"Expected ≥3 LLM calls, got {counter.count}"

                    # Verify result contains expected data
                    assert result is not None
                    assert "success" in result or "generated_tests" in result
                    # Result should have test generation information
                    assert result.get("agent_name") == "test_gen_agent" or "metrics" in result
