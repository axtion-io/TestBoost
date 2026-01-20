"""Integration tests for models and metrics functionality.

Tests cover Impact/TestRequirement models and MetricsCollector.
"""

import pytest


@pytest.mark.integration
class TestImpactModel:
    """Tests for Impact dataclass functionality."""

    def test_impact_requires_regression_for_bugfix(self, sample_bugfix_impact):
        """Bug fix impact should require regression test."""
        assert sample_bugfix_impact.requires_regression_test is True

    def test_impact_no_regression_for_feature(self, sample_impact):
        """Non-bugfix impact should not require regression test."""
        assert sample_impact.requires_regression_test is False

    def test_impact_requires_invariant_for_critical_business_rule(self, sample_impact):
        """Critical business rule should require invariant test."""
        from src.models.impact import ChangeCategory, RiskLevel

        assert sample_impact.category == ChangeCategory.BUSINESS_RULE
        assert sample_impact.risk_level == RiskLevel.BUSINESS_CRITICAL
        assert sample_impact.requires_invariant_test is True

    def test_impact_no_invariant_for_non_critical(self):
        """Non-critical change should not require invariant test."""
        from src.models.impact import ChangeCategory, Impact, RiskLevel, TestType

        impact = Impact(
            id="IMP-003",
            file_path="src/main/java/com/example/config/AppConfig.java",
            category=ChangeCategory.CONFIGURATION,
            risk_level=RiskLevel.NON_CRITICAL,
            affected_components=["AppConfig"],
            required_test_type=TestType.UNIT,
            change_summary="Updated logging configuration",
            is_bug_fix=False,
        )

        assert impact.requires_invariant_test is False

    def test_impact_to_dict_serialization(self, sample_impact):
        """Impact should serialize to dict correctly."""
        result = sample_impact.to_dict()

        assert result["id"] == "IMP-001"
        assert result["file_path"] == "src/main/java/com/example/service/PaymentService.java"
        assert result["category"] == "business_rule"
        assert result["risk_level"] == "business_critical"
        assert isinstance(result["affected_components"], list)
        assert result["is_bug_fix"] is False

    def test_impact_diff_lines_default(self):
        """Impact should have default diff_lines."""
        from src.models.impact import ChangeCategory, Impact, RiskLevel, TestType

        impact = Impact(
            id="IMP-004",
            file_path="test.java",
            category=ChangeCategory.OTHER,
            risk_level=RiskLevel.NON_CRITICAL,
            affected_components=[],
            required_test_type=TestType.UNIT,
            change_summary="Test",
        )

        assert impact.diff_lines == (0, 0)


@pytest.mark.integration
class TestTestRequirementModel:
    """Tests for TestRequirement dataclass functionality."""

    def test_test_requirement_to_dict(self):
        """TestRequirement should serialize to dict correctly."""
        from src.models.impact import ScenarioType, TestRequirement, TestType

        req = TestRequirement(
            id="TEST-001",
            impact_id="IMP-001",
            test_type=TestType.UNIT,
            scenario_type=ScenarioType.NOMINAL,
            description="Test payment processing",
            priority=1,
            target_class="PaymentService",
            suggested_test_name="shouldProcessPaymentSuccessfully",
            target_method="processPayment",
        )

        result = req.to_dict()

        assert result["id"] == "TEST-001"
        assert result["impact_id"] == "IMP-001"
        assert result["test_type"] == "unit"
        assert result["scenario_type"] == "nominal"
        assert result["priority"] == 1
        assert result["target_class"] == "PaymentService"
        assert result["suggested_test_name"] == "shouldProcessPaymentSuccessfully"
        assert result["target_method"] == "processPayment"

    def test_test_requirement_to_dict_optional_fields(self):
        """TestRequirement should handle optional fields in serialization."""
        from src.models.impact import ScenarioType, TestRequirement, TestType

        req = TestRequirement(
            id="TEST-002",
            impact_id="IMP-001",
            test_type=TestType.CONTROLLER,
            scenario_type=ScenarioType.EDGE_CASE,
            description="Test edge case",
            priority=2,
            target_class="UserController",
            # No suggested_test_name or target_method
        )

        result = req.to_dict()

        assert "suggested_test_name" not in result
        assert "target_method" not in result


@pytest.mark.integration
class TestDiffChunkModel:
    """Tests for DiffChunk dataclass functionality."""

    def test_diff_chunk_progress_percentage(self):
        """DiffChunk should calculate progress correctly."""
        from src.models.impact import DiffChunk

        chunk = DiffChunk(
            index=2,
            total_chunks=10,
            files=["file1.java", "file2.java"],
            content="diff content",
            line_count=50,
        )

        assert chunk.progress_pct == 30.0  # (2+1)/10 * 100

    def test_diff_chunk_progress_zero_total(self):
        """DiffChunk should handle zero total chunks."""
        from src.models.impact import DiffChunk

        chunk = DiffChunk(
            index=0,
            total_chunks=0,
            files=[],
            content="",
            line_count=0,
        )

        assert chunk.progress_pct == 100.0

    def test_diff_chunk_progress_last_chunk(self):
        """Last chunk should show 100% progress."""
        from src.models.impact import DiffChunk

        chunk = DiffChunk(
            index=4,
            total_chunks=5,
            files=["file.java"],
            content="diff content",
            line_count=100,
        )

        assert chunk.progress_pct == 100.0


@pytest.mark.integration
class TestMetricsCollector:
    """Tests for MetricsCollector functionality."""

    def test_counter_increment(self):
        """Counter should increment correctly."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.inc_counter("test_counter")
        collector.inc_counter("test_counter")
        collector.inc_counter("test_counter", value=3)

        assert collector._counters["test_counter"] == 5

    def test_counter_with_labels(self):
        """Counter should support labels."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.inc_counter("http_requests", labels={"method": "GET", "path": "/health"})
        collector.inc_counter("http_requests", labels={"method": "POST", "path": "/sessions"})

        # Should have separate keys for different labels
        assert len([k for k in collector._counters if k.startswith("http_requests")]) == 2

    def test_gauge_set_value(self):
        """Gauge should set value correctly."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.set_gauge("active_sessions", 5.0)
        collector.set_gauge("active_sessions", 10.0)  # Should overwrite

        assert collector._gauges["active_sessions"] == 10.0

    def test_histogram_observations(self):
        """Histogram should record observations."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.observe_histogram("request_duration", 0.1)
        collector.observe_histogram("request_duration", 0.2)
        collector.observe_histogram("request_duration", 0.3)

        assert len(collector._histograms["request_duration"]) == 3
        assert sum(collector._histograms["request_duration"]) == pytest.approx(0.6)

    def test_prometheus_format_output(self):
        """Should format metrics in Prometheus format."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.inc_counter("test_counter")
        collector.set_gauge("test_gauge", 42.0)

        output = collector.format_prometheus()

        assert "# TYPE test_counter counter" in output
        assert "test_counter 1" in output
        assert "# TYPE test_gauge gauge" in output
        assert "test_gauge 42.0" in output

    def test_prometheus_format_histogram(self):
        """Histogram should include sum and count in Prometheus format."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.observe_histogram("duration", 1.0)
        collector.observe_histogram("duration", 2.0)
        collector.observe_histogram("duration", 3.0)

        output = collector.format_prometheus()

        assert "# TYPE duration histogram" in output
        assert "duration_sum 6.0" in output
        assert "duration_count 3" in output

    def test_prometheus_format_empty(self):
        """Empty collector should return empty string."""
        from src.api.routers.metrics import MetricsCollector

        collector = MetricsCollector()
        output = collector.format_prometheus()

        assert output == ""


@pytest.mark.integration
class TestMetricsHelperFunctions:
    """Tests for metrics helper functions."""

    def test_record_workflow_duration(self):
        """Should record workflow duration metrics."""
        from src.api.routers.metrics import metrics, record_workflow_duration

        # Reset collector for clean test
        metrics._counters.clear()
        metrics._histograms.clear()

        record_workflow_duration("maven_maintenance", 5.5, status="success")

        # Should have counter and histogram entries
        assert any("workflow" in k for k in metrics._counters)
        assert any("workflow" in k for k in metrics._histograms)

    def test_record_llm_call_success(self):
        """Should record successful LLM calls."""
        from src.api.routers.metrics import metrics, record_llm_call

        metrics._counters.clear()

        record_llm_call("google-genai", "gemini-1.5-flash", success=True)

        assert any("llm_calls" in k and "success" in k for k in metrics._counters)

    def test_record_llm_call_failure(self):
        """Should record failed LLM calls with error counter."""
        from src.api.routers.metrics import metrics, record_llm_call

        metrics._counters.clear()

        record_llm_call("google-genai", "gemini-1.5-flash", success=False)

        assert any("llm_errors" in k for k in metrics._counters)

    def test_record_llm_rate_limit(self):
        """Should record LLM rate limit errors."""
        from src.api.routers.metrics import metrics, record_llm_rate_limit

        metrics._counters.clear()

        record_llm_rate_limit("openai")

        assert any("rate_limit" in k for k in metrics._counters)

    def test_set_active_sessions(self):
        """Should set active sessions gauge."""
        from src.api.routers.metrics import metrics, set_active_sessions

        set_active_sessions(15)

        assert metrics._gauges["testboost_active_sessions"] == 15.0

    def test_set_db_connection_pool(self):
        """Should set DB connection pool metrics."""
        from src.api.routers.metrics import metrics, set_db_connection_pool

        set_db_connection_pool(active=5, max_size=20)

        assert metrics._gauges["testboost_db_connection_pool_size"] == 5.0
        assert metrics._gauges["testboost_db_connection_pool_max"] == 20.0


@pytest.mark.integration
class TestChangeCategoryEnum:
    """Tests for ChangeCategory enum."""

    def test_all_categories_have_string_values(self):
        """All category enum values should be strings."""
        from src.models.impact import ChangeCategory

        for category in ChangeCategory:
            assert isinstance(category.value, str)

    def test_business_rule_category(self):
        """BUSINESS_RULE should have correct value."""
        from src.models.impact import ChangeCategory

        assert ChangeCategory.BUSINESS_RULE.value == "business_rule"

    def test_endpoint_category(self):
        """ENDPOINT should have correct value."""
        from src.models.impact import ChangeCategory

        assert ChangeCategory.ENDPOINT.value == "endpoint"


@pytest.mark.integration
class TestRiskLevelEnum:
    """Tests for RiskLevel enum."""

    def test_business_critical_value(self):
        """BUSINESS_CRITICAL should have correct value."""
        from src.models.impact import RiskLevel

        assert RiskLevel.BUSINESS_CRITICAL.value == "business_critical"

    def test_non_critical_value(self):
        """NON_CRITICAL should have correct value."""
        from src.models.impact import RiskLevel

        assert RiskLevel.NON_CRITICAL.value == "non_critical"


@pytest.mark.integration
class TestTestTypeEnum:
    """Tests for TestType enum."""

    def test_all_test_types(self):
        """Should have expected test types."""
        from src.models.impact import TestType

        test_types = [t.value for t in TestType]

        assert "unit" in test_types
        assert "controller" in test_types
        assert "integration" in test_types


@pytest.mark.integration
class TestScenarioTypeEnum:
    """Tests for ScenarioType enum."""

    def test_nominal_scenario(self):
        """NOMINAL should have correct value."""
        from src.models.impact import ScenarioType

        assert ScenarioType.NOMINAL.value == "nominal"

    def test_regression_scenario(self):
        """REGRESSION should have correct value."""
        from src.models.impact import ScenarioType

        assert ScenarioType.REGRESSION.value == "regression"
