# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the pure helpers of src.test_generation.generate_unit."""

from pathlib import Path
from types import SimpleNamespace

from src.test_generation.generate_unit import (
    _analyze_class,
    _build_framework_instructions,
    _detect_class_type,
    _detect_test_dependencies,
    _extract_token_usage,
    _get_test_file_path,
    _validate_generated_imports,
)

SERVICE_SOURCE = """
package com.example.service;

import com.example.repository.OrderRepository;
import java.math.BigDecimal;

@Service
public class OrderService {

    private final OrderRepository orderRepository;

    public OrderService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    public BigDecimal calculateTotal(Long orderId) {
        return BigDecimal.ZERO;
    }

    public void cancel(Long orderId) {
    }

    private void internalHelper() {
    }
}
"""

POM_JUNIT5 = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <dependencies>
    <dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId></dependency>
    <dependency><groupId>org.mockito</groupId><artifactId>mockito-core</artifactId></dependency>
    <dependency><groupId>org.assertj</groupId><artifactId>assertj-core</artifactId></dependency>
  </dependencies>
</project>
"""

POM_JUNIT4 = """<?xml version="1.0"?>
<project>
  <dependencies>
    <dependency><groupId>junit</groupId><artifactId>junit</artifactId></dependency>
  </dependencies>
</project>
"""


class TestAnalyzeClass:
    def test_service_with_constructor_injection(self):
        info = _analyze_class(SERVICE_SOURCE)
        assert info["class_name"] == "OrderService"
        assert info["package"] == "com.example.service"
        assert "Service" in info["annotations"]
        # Constructor dependency captured with its exact type
        assert {"type": "OrderRepository", "name": "orderRepository"} in info["dependencies"]
        # Public methods captured; private ones filtered out
        names = [m["name"] for m in info["methods"]]
        assert "calculateTotal" in names and "cancel" in names
        assert "internalHelper" not in names
        cancel = next(m for m in info["methods"] if m["name"] == "cancel")
        assert cancel["is_void"] is True

    def test_record(self):
        info = _analyze_class(
            "package com.x;\npublic record Money(BigDecimal amount, String currency) {}"
        )
        assert info["is_record"] is True
        assert info["class_name"] == "Money"
        assert any(d["type"] == "BigDecimal" for d in info["dependencies"])

    def test_autowired_field_dependency(self):
        src = (
            "package com.x;\npublic class A {\n"
            "  @Autowired private UserRepository userRepo;\n"
            "  public void run() {}\n}"
        )
        info = _analyze_class(src)
        assert {"type": "UserRepository", "name": "userRepo"} in info["dependencies"]


class TestDetectClassType:
    def test_by_annotation_and_name(self):
        cases = [
            ({"class_name": "X", "annotations": ["RestController"]}, "controller"),
            ({"class_name": "UserService", "annotations": []}, "service"),
            ({"class_name": "FooRepository", "annotations": []}, "repository"),
            ({"class_name": "User", "annotations": ["Entity"]}, "model"),
            ({"class_name": "StringUtils", "annotations": []}, "utility"),
        ]
        for info, expected in cases:
            assert _detect_class_type("", info) == expected, info


class TestDetectTestDependencies:
    def test_junit5_with_mockito_and_assertj(self, tmp_path):
        (tmp_path / "pom.xml").write_text(POM_JUNIT5)
        deps = _detect_test_dependencies(str(tmp_path))
        assert deps["framework"] == "junit5"
        assert deps["has_mockito"] is True
        assert deps["has_assertj"] is True

    def test_junit4(self, tmp_path):
        (tmp_path / "pom.xml").write_text(POM_JUNIT4)
        deps = _detect_test_dependencies(str(tmp_path))
        assert deps["framework"] == "junit4"
        assert deps["has_mockito"] is False

    def test_defaults_without_pom(self, tmp_path):
        deps = _detect_test_dependencies(str(tmp_path))
        assert deps["framework"] == "junit5"
        assert deps["available_deps"] == []


class TestFrameworkInstructions:
    def test_junit4_warns_against_junit5_constructs(self):
        text = _build_framework_instructions(
            {"framework": "junit4", "has_mockito": True, "has_assertj": False}
        )
        assert "JUnit 4" in text
        assert "@BeforeEach" in text  # mentioned as forbidden
        assert "RunWith(MockitoJUnitRunner" in text

    def test_junit5_uses_extension(self):
        text = _build_framework_instructions(
            {"framework": "junit5", "has_mockito": True, "has_assertj": True}
        )
        assert "JUnit 5" in text
        assert "ExtendWith(MockitoExtension" in text


class TestValidateGeneratedImports:
    def test_junit5_code_on_junit4_project(self):
        deps = {"framework": "junit4", "has_mockito": False, "has_assertj": False}
        code = (
            "import org.junit.jupiter.api.Test;\nimport org.mockito.Mock;\n"
            "import org.assertj.core.api.Assertions;\n@BeforeEach\n@ExtendWith(X.class)\n"
        )
        warnings = _validate_generated_imports(code, deps)
        joined = " ".join(warnings)
        assert "JUnit 5 imports" in joined
        assert "Mockito" in joined
        assert "AssertJ" in joined

    def test_clean_code_no_warnings(self):
        deps = {"framework": "junit5", "has_mockito": True, "has_assertj": True}
        code = "import org.junit.jupiter.api.Test;\nimport org.mockito.Mock;"
        assert _validate_generated_imports(code, deps) == []


class TestExtractTokenUsage:
    def test_from_response_metadata(self):
        resp = SimpleNamespace(response_metadata={
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
        assert _extract_token_usage(resp) == {
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
        }

    def test_from_usage_metadata(self):
        resp = SimpleNamespace(
            response_metadata={},
            usage_metadata=SimpleNamespace(input_tokens=7, output_tokens=3, total_tokens=10),
        )
        usage = _extract_token_usage(resp)
        assert usage["total_tokens"] == 10

    def test_missing_everywhere(self):
        usage = _extract_token_usage(object())
        assert usage == {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}


class TestGetTestFilePath:
    def test_maps_main_to_test_and_suffixes(self, tmp_path):
        src = tmp_path / "src/main/java/com/x/OrderService.java"
        result = _get_test_file_path(tmp_path, src)
        assert result == Path("src/test/java/com/x/OrderServiceTest.java")
