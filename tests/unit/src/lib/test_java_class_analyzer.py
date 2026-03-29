"""Unit tests for src.lib.java_class_analyzer."""



from src.lib.java_class_analyzer import (
    _extract_extends_implements,
    _extract_field_details,
    analyze_java_class,
    build_class_index,
    extract_test_examples,
)

# ---------------------------------------------------------------------------
# _extract_extends_implements
# ---------------------------------------------------------------------------

class TestExtractExtendsImplements:
    def test_simple_extends(self):
        src = "public class Foo extends Bar {\n}"
        ext, impl = _extract_extends_implements(src)
        assert ext == "Bar"
        assert impl == []

    def test_implements_only(self):
        src = "public class Foo implements Serializable, Cloneable {\n}"
        ext, impl = _extract_extends_implements(src)
        assert ext is None
        assert impl == ["Serializable", "Cloneable"]

    def test_extends_and_implements(self):
        src = "public class Foo extends Base implements Runnable, AutoCloseable {\n}"
        ext, impl = _extract_extends_implements(src)
        assert ext == "Base"
        assert "Runnable" in impl
        assert "AutoCloseable" in impl

    def test_generics_stripped(self):
        src = "public abstract class Foo<T> extends BaseClass<T> implements Iterable<T> {\n}"
        ext, impl = _extract_extends_implements(src)
        assert ext == "BaseClass"
        assert impl == ["Iterable"]

    def test_no_extends_no_implements(self):
        src = "public class Foo {\n}"
        ext, impl = _extract_extends_implements(src)
        assert ext is None
        assert impl == []


# ---------------------------------------------------------------------------
# _extract_field_details
# ---------------------------------------------------------------------------

class TestExtractFieldDetails:
    def test_basic_private_field(self):
        src = "private String name;\n"
        fields = _extract_field_details(src)
        names = [f["name"] for f in fields]
        assert "name" in names

    def test_field_with_annotation(self):
        src = "@Autowired\nprivate UserRepository userRepository;\n"
        fields = _extract_field_details(src)
        repo = next((f for f in fields if f["name"] == "userRepository"), None)
        assert repo is not None
        assert "Autowired" in repo["annotations"]

    def test_jpa_id_field(self):
        src = "@Id\n@GeneratedValue\nprivate Long id;\n"
        fields = _extract_field_details(src)
        id_field = next((f for f in fields if f["name"] == "id"), None)
        assert id_field is not None
        assert "Id" in id_field["annotations"]


# ---------------------------------------------------------------------------
# analyze_java_class
# ---------------------------------------------------------------------------

SERVICE_SOURCE = """\
package com.example.service;

import org.springframework.stereotype.Service;
import com.example.repository.AccountRepository;

@Service
public class AccountService extends AbstractService implements AccountApi {

    @Autowired
    private AccountRepository accountRepository;

    public AccountService(AccountRepository repo) {
        this.accountRepository = repo;
    }

    public Account findById(Long id) {
        return accountRepository.findById(id).orElse(null);
    }

    public void delete(Long id) {
        accountRepository.deleteById(id);
    }
}
"""

ENTITY_SOURCE = """\
package com.example.model;

import javax.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "accounts")
public class Account {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private BigDecimal balance;
}
"""


class TestAnalyzeJavaClass:
    def test_service_class(self):
        entry = analyze_java_class(SERVICE_SOURCE, "src/main/java/com/example/service/AccountService.java")
        assert entry["class_name"] == "AccountService"
        assert entry["package"] == "com.example.service"
        assert entry["category"] == "service"
        assert entry["extends"] == "AbstractService"
        assert "AccountApi" in entry["implements"]
        assert "Service" in entry["annotations"]

    def test_service_dependencies_detected(self):
        entry = analyze_java_class(SERVICE_SOURCE)
        dep_types = [d["type"] for d in entry["dependencies"]]
        assert "AccountRepository" in dep_types

    def test_service_methods(self):
        entry = analyze_java_class(SERVICE_SOURCE)
        method_names = [m["name"] for m in entry["methods"]]
        assert "findById" in method_names
        assert "delete" in method_names

    def test_entity_class(self):
        entry = analyze_java_class(ENTITY_SOURCE, "src/main/java/com/example/model/Account.java")
        assert entry["class_name"] == "Account"
        assert entry["is_jpa_entity"] is True
        assert entry["jpa_info"]["id_field"] == "id"
        assert entry["jpa_info"]["id_type"] == "Long"
        assert entry["jpa_info"]["has_generated_value"] is True

    def test_public_signatures_built(self):
        entry = analyze_java_class(SERVICE_SOURCE)
        assert "findById" in entry["public_signatures"]

    def test_relative_path_stored(self):
        path = "src/main/java/Foo.java"
        entry = analyze_java_class("public class Foo {}", path)
        assert entry["relative_path"] == path

    def test_record_detected(self):
        src = "public record Point(int x, int y) {}"
        entry = analyze_java_class(src)
        assert entry["is_record"] is True
        assert entry["class_name"] == "Point"


# ---------------------------------------------------------------------------
# build_class_index
# ---------------------------------------------------------------------------

class TestBuildClassIndex:
    def test_builds_index_from_dir(self, tmp_path):
        java_dir = tmp_path / "src" / "main" / "java"
        java_dir.mkdir(parents=True)
        (java_dir / "Foo.java").write_text("public class Foo {}", encoding="utf-8")
        (java_dir / "Bar.java").write_text("public class Bar {}", encoding="utf-8")

        index = build_class_index(
            str(tmp_path),
            ["src/main/java/Foo.java", "src/main/java/Bar.java"],
        )
        assert "Foo" in index
        assert "Bar" in index

    def test_skips_unreadable_files(self, tmp_path):
        # Pass a non-existent file — should not raise
        index = build_class_index(str(tmp_path), ["nonexistent/Foo.java"])
        assert index == {}

    def test_key_is_class_name(self, tmp_path):
        java_dir = tmp_path / "src"
        java_dir.mkdir()
        (java_dir / "MyService.java").write_text(
            "@Service\npublic class MyService {}", encoding="utf-8"
        )
        index = build_class_index(str(tmp_path), ["src/MyService.java"])
        assert "MyService" in index
        assert index["MyService"]["category"] == "service"


# ---------------------------------------------------------------------------
# extract_test_examples
# ---------------------------------------------------------------------------

class TestExtractTestExamples:
    def test_returns_empty_when_no_test_dir(self, tmp_path):
        examples = extract_test_examples(str(tmp_path))
        assert examples == []

    def test_finds_test_files(self, tmp_path):
        test_dir = tmp_path / "src" / "test" / "java" / "com" / "example"
        test_dir.mkdir(parents=True)
        (test_dir / "UserServiceTest.java").write_text(
            "class UserServiceTest { @Test void test() {} }", encoding="utf-8"
        )
        examples = extract_test_examples(str(tmp_path), max_examples=3)
        assert len(examples) == 1
        assert "UserServiceTest" in examples[0]["path"]

    def test_max_lines_respected(self, tmp_path):
        test_dir = tmp_path / "src" / "test" / "java"
        test_dir.mkdir(parents=True)
        content = "\n".join(f"// line {i}" for i in range(300))
        (test_dir / "FooTest.java").write_text(content, encoding="utf-8")
        examples = extract_test_examples(str(tmp_path), max_lines=50)
        assert len(examples[0]["content"].splitlines()) <= 50
