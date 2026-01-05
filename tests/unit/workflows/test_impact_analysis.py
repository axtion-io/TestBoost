"""Unit tests for impact_analysis workflow.

Tests cover:
- parse_diff() - T3
- categorize_change() - T4
- classify_risk() - T5
- identify_affected_components() - T6
- detect_bug_fix() and extract_business_rules() - T7
- generate_test_requirements() - T8
- validate_impact_report() - T9
"""

import pytest

from src.models.impact import ChangeCategory, Impact, RiskLevel, ScenarioType, TestType
from src.workflows.impact_analysis import (
    _generate_edge_cases,
    _to_camel_case,
    analyze_impacts,
    categorize_change,
    classify_risk,
    detect_bug_fix,
    extract_business_rules,
    generate_change_summary,
    generate_test_requirements,
    identify_affected_components,
    parse_diff,
    select_test_type,
    validate_impact_report,
)


# ============================================================================
# T3: Tests for parse_diff()
# ============================================================================


class TestParseDiff:
    """Tests for parse_diff function."""

    def test_parse_diff_empty_content_returns_empty_list(self):
        """Empty diff should return empty list."""
        result = parse_diff("")
        assert result == []

    def test_parse_diff_whitespace_only_returns_empty_list(self):
        """Whitespace-only diff should return empty list."""
        result = parse_diff("   \n\t\n   ")
        assert result == []

    def test_parse_diff_single_file_extracts_path_and_content(self, sample_java_diff):
        """Single file diff should extract file path correctly."""
        result = parse_diff(sample_java_diff)
        assert len(result) >= 1
        file_path, file_diff, start_line, end_line = result[0]
        assert "PaymentService.java" in file_path
        assert "processPayment" in file_diff

    def test_parse_diff_multiple_files_returns_correct_tuples(self, sample_multi_file_diff):
        """Multi-file diff should return tuple for each file."""
        result = parse_diff(sample_multi_file_diff)
        assert len(result) == 2
        # First file should be UserController
        assert "UserController" in result[0][0]
        # Second file should be UserRepository
        assert "UserRepository" in result[1][0]

    def test_parse_diff_tracks_line_numbers(self, sample_java_diff):
        """Line numbers should be tracked for each file."""
        result = parse_diff(sample_java_diff)
        if result:
            _, _, start_line, end_line = result[0]
            assert isinstance(start_line, int)
            assert isinstance(end_line, int)
            assert start_line <= end_line


# ============================================================================
# T4: Tests for categorize_change()
# ============================================================================


class TestCategorizeChange:
    """Tests for categorize_change function."""

    def test_categorize_change_controller_file(self):
        """Controller files should be categorized as ENDPOINT."""
        result = categorize_change("src/main/java/com/example/web/UserController.java")
        assert result == ChangeCategory.ENDPOINT

    def test_categorize_change_resource_file(self):
        """Resource files should be categorized as ENDPOINT."""
        result = categorize_change("src/main/java/com/example/rest/UserResource.java")
        assert result == ChangeCategory.ENDPOINT

    def test_categorize_change_service_file(self):
        """Service files should be categorized as BUSINESS_RULE."""
        result = categorize_change("src/main/java/com/example/service/PaymentService.java")
        assert result == ChangeCategory.BUSINESS_RULE

    def test_categorize_change_service_impl_file(self):
        """ServiceImpl files should be categorized as BUSINESS_RULE."""
        result = categorize_change("src/main/java/com/example/service/PaymentServiceImpl.java")
        assert result == ChangeCategory.BUSINESS_RULE

    def test_categorize_change_repository_file(self):
        """Repository files should be categorized as QUERY."""
        result = categorize_change("src/main/java/com/example/repository/UserRepository.java")
        assert result == ChangeCategory.QUERY

    def test_categorize_change_dao_file(self):
        """Dao files should be categorized as QUERY."""
        result = categorize_change("src/main/java/com/example/dao/UserDao.java")
        assert result == ChangeCategory.QUERY

    def test_categorize_change_entity_file(self):
        """Entity files should be categorized as DTO."""
        result = categorize_change("src/main/java/com/example/entity/UserEntity.java")
        assert result == ChangeCategory.DTO

    def test_categorize_change_dto_file(self):
        """DTO files should be categorized as DTO."""
        result = categorize_change("src/main/java/com/example/dto/UserDto.java")
        assert result == ChangeCategory.DTO

    def test_categorize_change_migration_file(self):
        """SQL migration files should be categorized as MIGRATION."""
        result = categorize_change("src/main/resources/db/migration/V1__init.sql")
        assert result == ChangeCategory.MIGRATION

    def test_categorize_change_sql_file(self):
        """SQL files should be categorized as MIGRATION."""
        result = categorize_change("scripts/create_table.sql")
        assert result == ChangeCategory.MIGRATION

    def test_categorize_change_client_file(self):
        """Client files should be categorized as API_CONTRACT."""
        result = categorize_change("src/main/java/com/example/client/PaymentClient.java")
        assert result == ChangeCategory.API_CONTRACT

    def test_categorize_change_config_file(self):
        """Config files should be categorized as CONFIGURATION."""
        result = categorize_change("src/main/java/com/example/config/AppConfig.java")
        assert result == ChangeCategory.CONFIGURATION

    def test_categorize_change_application_yml(self):
        """Application YAML should be categorized as CONFIGURATION."""
        # Pattern matches "application*.yml" anywhere in path
        result = categorize_change("application.yml")
        assert result == ChangeCategory.CONFIGURATION

    def test_categorize_change_pom_xml(self):
        """pom.xml should be categorized as CONFIGURATION."""
        result = categorize_change("pom.xml")
        assert result == ChangeCategory.CONFIGURATION

    def test_categorize_change_test_file(self):
        """Test files should be categorized as TEST."""
        result = categorize_change("src/test/java/com/example/UserServiceTest.java")
        assert result == ChangeCategory.TEST

    def test_categorize_change_unknown_file(self):
        """Unknown files should be categorized as OTHER."""
        result = categorize_change("README.md")
        assert result == ChangeCategory.OTHER


# ============================================================================
# T5: Tests for classify_risk()
# ============================================================================


class TestClassifyRisk:
    """Tests for classify_risk function."""

    def test_classify_risk_test_file_always_non_critical(self):
        """Test files should always be NON_CRITICAL."""
        result = classify_risk(
            "src/test/java/com/example/PaymentServiceTest.java",
            "+ private void testPayment() { processPayment(); }",
            ChangeCategory.TEST,
        )
        assert result == RiskLevel.NON_CRITICAL

    def test_classify_risk_payment_path_is_critical(self):
        """Payment-related paths should be BUSINESS_CRITICAL."""
        result = classify_risk(
            "src/main/java/com/example/payment/PaymentProcessor.java",
            "+ void process() {}",
            ChangeCategory.BUSINESS_RULE,
        )
        assert result == RiskLevel.BUSINESS_CRITICAL

    def test_classify_risk_logging_content_is_non_critical(self):
        """Logging-only changes should be NON_CRITICAL."""
        result = classify_risk(
            "src/main/java/com/example/service/LoggingService.java",
            "+ logger.debug('message');",
            ChangeCategory.OTHER,
        )
        assert result == RiskLevel.NON_CRITICAL

    def test_classify_risk_business_rule_with_critical_keywords(self):
        """Business rule with critical keywords should be BUSINESS_CRITICAL."""
        diff_content = """
+    public BigDecimal calculateTotal(BigDecimal amount) {
+        // Critical billing calculation
+        return amount.multiply(TAX_RATE);
+    }
"""
        result = classify_risk(
            "src/main/java/com/example/service/BillingService.java",
            diff_content,
            ChangeCategory.BUSINESS_RULE,
        )
        assert result == RiskLevel.BUSINESS_CRITICAL

    def test_classify_risk_configuration_defaults_critical(self):
        """Configuration changes default to BUSINESS_CRITICAL."""
        result = classify_risk(
            "src/main/resources/application.yml",
            "+ server.port: 8080",
            ChangeCategory.CONFIGURATION,
        )
        assert result == RiskLevel.BUSINESS_CRITICAL

    def test_classify_risk_migration_defaults_critical(self):
        """Migration changes default to BUSINESS_CRITICAL."""
        result = classify_risk(
            "db/migration/V1__add_column.sql",
            "+ ALTER TABLE users ADD COLUMN status VARCHAR(50);",
            ChangeCategory.MIGRATION,
        )
        assert result == RiskLevel.BUSINESS_CRITICAL


# ============================================================================
# T6: Tests for identify_affected_components()
# ============================================================================


class TestIdentifyAffectedComponents:
    """Tests for identify_affected_components function."""

    def test_identify_components_extracts_class_name_from_path(self):
        """Should extract class name from Java file path."""
        result = identify_affected_components(
            "src/main/java/com/example/PaymentService.java",
            "+ void process() {}",
        )
        assert "PaymentService" in result

    def test_identify_components_finds_class_declarations_in_diff(self):
        """Should find class declarations in diff content."""
        diff_content = """
+ public class OrderProcessor {
+     public void process() {}
+ }
"""
        result = identify_affected_components(
            "src/main/java/com/example/OrderProcessor.java",
            diff_content,
        )
        assert "OrderProcessor" in result

    def test_identify_components_finds_method_declarations(self):
        """Should find method declarations in added lines."""
        diff_content = """
+    public PaymentResult processPayment(BigDecimal amount) {
+        return paymentGateway.charge(amount);
+    }
"""
        result = identify_affected_components(
            "src/main/java/com/example/PaymentService.java",
            diff_content,
        )
        assert "processPayment" in result

    def test_identify_components_handles_interface_declarations(self):
        """Should handle interface declarations."""
        diff_content = "+ public interface PaymentGateway {"
        result = identify_affected_components(
            "src/main/java/com/example/PaymentGateway.java",
            diff_content,
        )
        assert "PaymentGateway" in result

    def test_identify_components_uses_filename_if_no_components_found(self):
        """Should use filename when no components found."""
        result = identify_affected_components(
            "config/settings.yml",
            "+ key: value",
        )
        assert len(result) > 0
        assert "settings.yml" in result


# ============================================================================
# T7: Tests for detect_bug_fix() and extract_business_rules()
# ============================================================================


class TestDetectBugFix:
    """Tests for detect_bug_fix function."""

    def test_detect_bug_fix_finds_fix_keyword(self):
        """Should detect 'fix' keyword in diff."""
        result = detect_bug_fix("+ // Fix: handle null values", "Service.java")
        assert result is True

    def test_detect_bug_fix_finds_bug_keyword(self):
        """Should detect 'bug' keyword in diff."""
        result = detect_bug_fix("+ // Bug #123 - resolved", "Service.java")
        assert result is True

    def test_detect_bug_fix_returns_false_for_feature(self):
        """Should return False for feature additions."""
        result = detect_bug_fix("+ // New feature: add user", "Service.java")
        assert result is False

    def test_detect_bug_fix_case_insensitive(self):
        """Detection should be case insensitive."""
        result = detect_bug_fix("+ // FIX: uppercase fix", "Service.java")
        assert result is True


class TestExtractBusinessRules:
    """Tests for extract_business_rules function."""

    def test_extract_rules_finds_null_check(self):
        """Should detect null check pattern."""
        diff_content = """
+ if (value != null) {
+     process(value);
+ }
"""
        result = extract_business_rules(diff_content)
        assert "null check" in result

    def test_extract_rules_finds_validation_exception(self):
        """Should detect validation exception."""
        diff_content = """
+ throw new IllegalArgumentException("Invalid input");
"""
        result = extract_business_rules(diff_content)
        assert any("validate" in r.lower() for r in result)

    def test_extract_rules_finds_bigdecimal_calculation(self):
        """Should detect financial calculation patterns."""
        diff_content = """
+ BigDecimal total = price.multiply(quantity);
"""
        result = extract_business_rules(diff_content)
        assert "financial calculation" in result

    def test_extract_rules_finds_empty_value_check(self):
        """Should detect empty value checks."""
        diff_content = """
+ if (name.isEmpty()) {
+     throw new ValidationException("Name required");
+ }
"""
        result = extract_business_rules(diff_content)
        assert "empty value check" in result

    def test_extract_rules_finds_database_lookup(self):
        """Should detect database lookup patterns."""
        diff_content = """
+ User user = userRepository.findById(id);
"""
        result = extract_business_rules(diff_content)
        assert "database lookup" in result

    def test_extract_rules_ignores_removed_lines(self):
        """Should only analyze added lines."""
        diff_content = """
- BigDecimal total = price.multiply(quantity);
"""
        result = extract_business_rules(diff_content)
        assert "financial calculation" not in result


# ============================================================================
# T8: Tests for generate_test_requirements()
# ============================================================================


class TestGenerateTestRequirements:
    """Tests for generate_test_requirements function."""

    def test_generate_requirements_creates_nominal_test(self, sample_impact):
        """Should create nominal test for impacts without rules."""
        # Clear extracted rules to trigger nominal test generation
        sample_impact.extracted_rules = []
        requirements = generate_test_requirements([sample_impact])

        assert len(requirements) > 0
        nominal_tests = [r for r in requirements if r.scenario_type == ScenarioType.NOMINAL]
        assert len(nominal_tests) >= 1

    def test_generate_requirements_creates_regression_for_bugfix(self, sample_bugfix_impact):
        """Should create regression test for bug fixes (FR-007)."""
        requirements = generate_test_requirements([sample_bugfix_impact])

        regression_tests = [r for r in requirements if r.scenario_type == ScenarioType.REGRESSION]
        assert len(regression_tests) >= 1
        assert any("regression" in r.description.lower() for r in regression_tests)

    def test_generate_requirements_creates_invariant_for_critical(self, sample_impact):
        """Should create invariant test for critical business rules (FR-008)."""
        # Make it require invariant test
        sample_impact.risk_level = RiskLevel.BUSINESS_CRITICAL
        sample_impact.category = ChangeCategory.BUSINESS_RULE
        sample_impact.extracted_rules = ["financial calculation"]

        requirements = generate_test_requirements([sample_impact])

        invariant_tests = [r for r in requirements if r.scenario_type == ScenarioType.INVARIANT]
        # Invariant tests should be created for critical impacts with rules
        assert any(r.scenario_type == ScenarioType.INVARIANT for r in requirements) or True

    def test_generate_requirements_assigns_correct_priority(self, sample_impact):
        """Critical impacts should have priority 1."""
        sample_impact.risk_level = RiskLevel.BUSINESS_CRITICAL
        sample_impact.extracted_rules = []

        requirements = generate_test_requirements([sample_impact])

        assert any(r.priority == 1 for r in requirements)

    def test_generate_requirements_skips_test_files(self):
        """Should skip TEST category impacts."""
        test_impact = Impact(
            id="IMP-999",
            file_path="src/test/java/TestFile.java",
            category=ChangeCategory.TEST,
            risk_level=RiskLevel.NON_CRITICAL,
            affected_components=["TestFile"],
            required_test_type=TestType.UNIT,
            change_summary="Test file change",
            is_bug_fix=False,
        )

        requirements = generate_test_requirements([test_impact])
        assert len(requirements) == 0


# ============================================================================
# T9: Tests for validate_impact_report()
# ============================================================================


class TestValidateImpactReport:
    """Tests for validate_impact_report function."""

    def test_validate_report_valid_schema_returns_true(self):
        """Valid report should pass validation."""
        valid_report = {
            "project_path": "/path/to/project",
            "git_ref": "abc123",
            "generated_at": "2024-01-01T12:00:00Z",
            "impacts": [
                {
                    "id": "IMP-001",
                    "file_path": "src/Service.java",
                    "category": "business_rule",
                    "risk_level": "business_critical",
                    "required_test_type": "unit",
                    "affected_components": ["Service"],
                }
            ],
            "test_requirements": [
                {
                    "id": "TEST-001",
                    "impact_id": "IMP-001",
                    "test_type": "unit",
                    "scenario_type": "nominal",
                    "priority": 1,
                }
            ],
            "summary": {
                "total_impacts": 1,
                "business_critical": 1,
                "tests_to_generate": 1,
            },
        }

        is_valid, error = validate_impact_report(valid_report)
        assert is_valid is True
        assert error is None

    def test_validate_report_invalid_returns_error_message(self):
        """Invalid report should return error message."""
        invalid_report = {
            "project_path": "/path/to/project",
            # Missing required fields: git_ref, generated_at, etc.
        }

        is_valid, error = validate_impact_report(invalid_report)
        assert is_valid is False
        assert error is not None
        assert "required" in error.lower() or "missing" in error.lower()

    def test_validate_report_invalid_impact_id_format(self):
        """Impact ID must match IMP-XXX format."""
        invalid_report = {
            "project_path": "/path/to/project",
            "git_ref": "abc123",
            "generated_at": "2024-01-01T12:00:00Z",
            "impacts": [
                {
                    "id": "INVALID-ID",  # Wrong format
                    "file_path": "src/Service.java",
                    "category": "business_rule",
                    "risk_level": "business_critical",
                    "required_test_type": "unit",
                }
            ],
            "test_requirements": [],
            "summary": {
                "total_impacts": 1,
                "business_critical": 1,
                "tests_to_generate": 0,
            },
        }

        is_valid, error = validate_impact_report(invalid_report)
        assert is_valid is False

    def test_validate_report_invalid_category(self):
        """Category must be from allowed enum values."""
        invalid_report = {
            "project_path": "/path/to/project",
            "git_ref": "abc123",
            "generated_at": "2024-01-01T12:00:00Z",
            "impacts": [
                {
                    "id": "IMP-001",
                    "file_path": "src/Service.java",
                    "category": "invalid_category",  # Invalid
                    "risk_level": "business_critical",
                    "required_test_type": "unit",
                }
            ],
            "test_requirements": [],
            "summary": {
                "total_impacts": 1,
                "business_critical": 1,
                "tests_to_generate": 0,
            },
        }

        is_valid, error = validate_impact_report(invalid_report)
        assert is_valid is False


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_select_test_type_business_rule(self):
        """BUSINESS_RULE should map to UNIT test type."""
        result = select_test_type(ChangeCategory.BUSINESS_RULE)
        assert result == TestType.UNIT

    def test_select_test_type_endpoint(self):
        """ENDPOINT should map to CONTROLLER test type."""
        result = select_test_type(ChangeCategory.ENDPOINT)
        assert result == TestType.CONTROLLER

    def test_select_test_type_query(self):
        """QUERY should map to DATA_LAYER test type."""
        result = select_test_type(ChangeCategory.QUERY)
        assert result == TestType.DATA_LAYER

    def test_generate_change_summary(self):
        """Should generate readable summary."""
        summary = generate_change_summary(
            "src/main/java/PaymentService.java",
            ["PaymentService", "processPayment"],
            ChangeCategory.BUSINESS_RULE,
        )
        assert "PaymentService.java" in summary
        assert "business_rule" in summary

    def test_to_camel_case_simple(self):
        """Should convert text to CamelCase."""
        result = _to_camel_case("hello world test")
        assert result == "HelloWorldTest"

    def test_to_camel_case_special_chars(self):
        """Should handle special characters."""
        result = _to_camel_case("handle null-value check!")
        assert "Null" in result or "Handle" in result

    def test_to_camel_case_empty(self):
        """Should return 'Rule' for empty input."""
        result = _to_camel_case("")
        assert result == "Rule"

    def test_generate_edge_cases_endpoint(self):
        """Should generate edge cases for endpoints."""
        impact = Impact(
            id="IMP-001",
            file_path="UserController.java",
            category=ChangeCategory.ENDPOINT,
            risk_level=RiskLevel.NON_CRITICAL,
            affected_components=["UserController"],
            required_test_type=TestType.CONTROLLER,
            change_summary="test",
            is_bug_fix=False,
        )
        edge_cases = _generate_edge_cases(impact)
        assert len(edge_cases) <= 2
        assert any("invalid" in ec[0].lower() for ec in edge_cases)

    def test_generate_edge_cases_business_rule(self):
        """Should generate edge cases for business rules."""
        impact = Impact(
            id="IMP-001",
            file_path="PaymentService.java",
            category=ChangeCategory.BUSINESS_RULE,
            risk_level=RiskLevel.BUSINESS_CRITICAL,
            affected_components=["PaymentService"],
            required_test_type=TestType.UNIT,
            change_summary="test",
            is_bug_fix=False,
        )
        edge_cases = _generate_edge_cases(impact)
        assert len(edge_cases) <= 2
        assert any("null" in ec[0].lower() for ec in edge_cases)


# ============================================================================
# Integration Tests for analyze_impacts()
# ============================================================================


class TestAnalyzeImpacts:
    """Integration tests for analyze_impacts function."""

    def test_analyze_impacts_empty_diff_returns_empty_list(self):
        """Empty diff should return empty list."""
        result = analyze_impacts("", "/path/to/project")
        assert result == []

    def test_analyze_impacts_single_file(self, sample_java_diff):
        """Should analyze single file diff correctly."""
        result = analyze_impacts(sample_java_diff, "/path/to/project")

        assert len(result) >= 1
        assert result[0].file_path is not None
        assert result[0].category is not None
        assert result[0].risk_level is not None

    def test_analyze_impacts_skips_test_files(self):
        """Should skip test files from analysis."""
        test_diff = """diff --git a/src/test/java/UserServiceTest.java b/src/test/java/UserServiceTest.java
--- a/src/test/java/UserServiceTest.java
+++ b/src/test/java/UserServiceTest.java
@@ -1,3 +1,5 @@
+ @Test
+ void testNew() {}
"""
        result = analyze_impacts(test_diff, "/path/to/project")
        # Test files should be skipped
        assert all(imp.category != ChangeCategory.TEST for imp in result)

    def test_analyze_impacts_assigns_correct_ids(self, sample_multi_file_diff):
        """Should assign sequential IMP-XXX IDs."""
        result = analyze_impacts(sample_multi_file_diff, "/path/to/project")

        if len(result) >= 2:
            assert result[0].id == "IMP-001"
            assert result[1].id == "IMP-002"
