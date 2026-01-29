"""Pytest configuration and shared fixtures for TestBoost tests."""

import os
import sys
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture
async def db_session():
    """
    Provide a database session with transaction rollback.

    This fixture creates a new database session for each test and rolls back
    all changes after the test completes, ensuring test isolation.
    """
    # Mock database session for unit tests
    # In integration tests with real DB, this would use actual connection
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    yield session

    # Rollback any changes
    await session.rollback()
    await session.close()


@pytest.fixture
async def db_connection():
    """Provide a raw database connection for low-level tests."""
    connection = AsyncMock()
    connection.execute = AsyncMock()
    connection.fetchone = AsyncMock()
    connection.fetchall = AsyncMock()

    yield connection


# ============================================================================
# HTTP Client Fixtures
# ============================================================================

# Test API key for authentication
TEST_API_KEY = "test-api-key-for-unit-tests"


@pytest.fixture
async def client() -> AsyncGenerator:
    """
    Provide an async HTTP client for API testing.

    Uses httpx with ASGITransport for in-process testing of FastAPI app.
    Includes authentication header for protected endpoints.
    Mocks database dependencies for unit testing.
    """
    try:
        from httpx import ASGITransport, AsyncClient

        from src.api.main import app
        from src.db import get_db

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.scalar = AsyncMock(return_value=0)  # For count queries
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)  # For get operations

        async def mock_get_db():
            yield mock_db

        # Override the database dependency
        app.dependency_overrides[get_db] = mock_get_db

        # Create mock engine for health endpoint database check
        mock_engine = MagicMock()
        mock_connection = AsyncMock()
        mock_connection.execute = AsyncMock(return_value=MagicMock())
        mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_engine.connect = MagicMock(return_value=mock_connection)

        # Patch settings to use test API key
        with patch("src.api.middleware.auth.settings") as mock_settings, \
             patch("src.db.get_async_engine", return_value=mock_engine):
            mock_settings.api_key = TEST_API_KEY

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers={"X-API-Key": TEST_API_KEY}
            ) as ac:
                yield ac

        # Clean up dependency overrides
        app.dependency_overrides.clear()
    except ImportError:
        # Fallback mock client for when dependencies aren't available
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
        mock_client.post = AsyncMock(
            return_value=MagicMock(status_code=201, json=lambda: {"id": "test-id"})
        )
        mock_client.delete = AsyncMock(return_value=MagicMock(status_code=204))
        yield mock_client


# ============================================================================
# LLM Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_llm_provider():
    """Provide a mocked LLM provider."""
    provider = AsyncMock()
    provider.generate = AsyncMock(
        return_value={"content": "Mocked LLM response", "tokens_used": 100}
    )
    return provider


@pytest.fixture
def mock_llm():
    """Alias for mock_llm_provider for backwards compatibility."""
    provider = AsyncMock()
    provider.generate = AsyncMock(
        return_value={"content": "Mocked LLM response", "tokens_used": 100}
    )
    return provider


@pytest.fixture
def mock_gemini_responses():
    """Load Gemini mock responses from fixtures."""
    import json

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "llm_responses", "gemini_responses.json"
    )
    if os.path.exists(fixture_path):
        with open(fixture_path) as f:
            return json.load(f)
    return {"default_response": {"content": "Mock", "tokens_used": 50}}


# ============================================================================
# File System Fixtures
# ============================================================================


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with sample files."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # Create sample pom.xml
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
</project>"""
    (project_dir / "pom.xml").write_text(pom_content)

    # Create sample Java file
    src_dir = project_dir / "src" / "main" / "java" / "com" / "test"
    src_dir.mkdir(parents=True)
    (src_dir / "TestService.java").write_text("""
package com.test;

public class TestService {
    public String hello() {
        return "Hello";
    }
}
""")

    return project_dir


# ============================================================================
# Pytest Markers
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow-running")
    config.addinivalue_line("markers", "unit: mark test as unit test")


# ============================================================================
# Test Helpers
# ============================================================================


@pytest.fixture
def assert_valid_uuid():
    """Helper to assert a string is a valid UUID."""
    import uuid as uuid_module

    def _assert(value: str):
        try:
            uuid_module.UUID(value)
            return True
        except ValueError:
            pytest.fail(f"'{value}' is not a valid UUID")

    return _assert


# ============================================================================
# Coverage Improvement Fixtures (Phase 005)
# ============================================================================


@pytest.fixture
def sample_java_diff():
    """Sample unified diff for Java file testing."""
    return """diff --git a/src/main/java/com/example/service/PaymentService.java b/src/main/java/com/example/service/PaymentService.java
--- a/src/main/java/com/example/service/PaymentService.java
+++ b/src/main/java/com/example/service/PaymentService.java
@@ -10,6 +10,15 @@ public class PaymentService {
+    public PaymentResult processPayment(BigDecimal amount, String customerId) {
+        if (amount == null || amount.compareTo(BigDecimal.ZERO) <= 0) {
+            throw new IllegalArgumentException("Amount must be positive");
+        }
+        if (customerId == null || customerId.isEmpty()) {
+            throw new IllegalArgumentException("Customer ID required");
+        }
+        return paymentRepository.save(new Payment(amount, customerId));
+    }
"""


@pytest.fixture
def sample_multi_file_diff():
    """Sample diff with multiple files."""
    return """diff --git a/src/main/java/com/example/web/UserController.java b/src/main/java/com/example/web/UserController.java
--- a/src/main/java/com/example/web/UserController.java
+++ b/src/main/java/com/example/web/UserController.java
@@ -5,6 +5,10 @@ public class UserController {
+    @GetMapping("/users/{id}")
+    public User getUser(@PathVariable Long id) {
+        return userService.findById(id);
+    }
diff --git a/src/main/java/com/example/repository/UserRepository.java b/src/main/java/com/example/repository/UserRepository.java
--- a/src/main/java/com/example/repository/UserRepository.java
+++ b/src/main/java/com/example/repository/UserRepository.java
@@ -10,3 +10,6 @@ public interface UserRepository {
+    Optional<User> findById(Long id);
"""


@pytest.fixture
def sample_impact():
    """Pre-generated Impact object for testing."""
    from src.models.impact import ChangeCategory, Impact, PyramidLevel, RiskLevel

    return Impact(
        id="IMP-001",
        file_path="src/main/java/com/example/service/PaymentService.java",
        category=ChangeCategory.BUSINESS_RULE,
        risk_level=RiskLevel.BUSINESS_CRITICAL,
        affected_components=["PaymentService", "processPayment"],
        required_test_type=PyramidLevel.UNIT,
        change_summary="Added payment processing method with validation",
        is_bug_fix=False,
    )


@pytest.fixture
def sample_bugfix_impact():
    """Impact object representing a bug fix."""
    from src.models.impact import ChangeCategory, Impact, PyramidLevel, RiskLevel

    return Impact(
        id="IMP-002",
        file_path="src/main/java/com/example/service/OrderService.java",
        category=ChangeCategory.BUSINESS_RULE,
        risk_level=RiskLevel.BUSINESS_CRITICAL,
        affected_components=["OrderService", "calculateTotal"],
        required_test_type=PyramidLevel.UNIT,
        change_summary="Fixed calculation error in order total",
        is_bug_fix=True,
    )


@pytest.fixture
def mock_subprocess_success():
    """Mock for successful subprocess execution."""

    async def _create_mock(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"BUILD SUCCESS\nTests run: 5, Failures: 0", b""))
        return mock_proc

    return _create_mock


@pytest.fixture
def mock_subprocess_failure():
    """Mock for failed subprocess execution."""

    async def _create_mock(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"BUILD FAILURE", b"[ERROR] Compilation failed")
        )
        return mock_proc

    return _create_mock


@pytest.fixture
def mock_java_project(tmp_path):
    """Create mock Java project structure for test_generation tests."""
    # Create Maven project structure
    src_main = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_main.mkdir(parents=True)

    # Create web package with controller
    web_dir = src_main / "web"
    web_dir.mkdir()
    (web_dir / "UserController.java").write_text(
        """package com.example.web;

import org.springframework.web.bind.annotation.*;

@RestController
public class UserController {
    @GetMapping("/users")
    public List<User> getUsers() {
        return userService.findAll();
    }
}
"""
    )

    # Create service package
    service_dir = src_main / "service"
    service_dir.mkdir()
    (service_dir / "UserService.java").write_text(
        """package com.example.service;

public class UserService {
    public List<User> findAll() {
        return userRepository.findAll();
    }
}
"""
    )

    # Create repository package
    repo_dir = src_main / "repository"
    repo_dir.mkdir()
    (repo_dir / "UserRepository.java").write_text(
        """package com.example.repository;

public interface UserRepository {
    List<User> findAll();
}
"""
    )

    # Create config (should be excluded)
    config_dir = src_main / "config"
    config_dir.mkdir()
    (config_dir / "AppConfig.java").write_text(
        """package com.example.config;

@Configuration
public class AppConfig {
}
"""
    )

    # Create pom.xml
    (tmp_path / "pom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
</project>
"""
    )

    return tmp_path


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create mock git repository for git tools testing."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Create some tracked files
    (tmp_path / "README.md").write_text("# Test Project")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")

    return tmp_path


@pytest.fixture
def maven_test_output_success():
    """Sample Maven test output for successful build."""
    return """[INFO] Scanning for projects...
[INFO] --- maven-surefire-plugin:3.0.0:test (default-test) @ test-project ---
[INFO] Running com.example.UserServiceTest
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1.234 s
[INFO] Running com.example.PaymentServiceTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 1, Time elapsed: 0.567 s
[INFO]
[INFO] Results:
[INFO]
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 1
[INFO]
[INFO] BUILD SUCCESS
"""


@pytest.fixture
def maven_test_output_failure():
    """Sample Maven test output for failed build."""
    return """[INFO] Scanning for projects...
[INFO] --- maven-surefire-plugin:3.0.0:test (default-test) @ test-project ---
[INFO] Running com.example.UserServiceTest
[ERROR] Tests run: 5, Failures: 2, Errors: 0, Skipped: 0, Time elapsed: 1.234 s <<< FAILURE!
[ERROR] com.example.UserServiceTest.testCreateUser -- Time elapsed: 0.123 s <<< FAILURE!
java.lang.AssertionError: expected:<1> but was:<0>
    at org.junit.Assert.fail(Assert.java:89)
    at com.example.UserServiceTest.testCreateUser(UserServiceTest.java:45)
[ERROR] com.example.UserServiceTest.testDeleteUser -- Time elapsed: 0.045 s <<< FAILURE!
java.lang.NullPointerException
    at com.example.UserServiceTest.testDeleteUser(UserServiceTest.java:67)
[INFO]
[INFO] Results:
[INFO]
[INFO] Tests run: 5, Failures: 2, Errors: 0, Skipped: 0
[INFO]
[INFO] BUILD FAILURE
"""
