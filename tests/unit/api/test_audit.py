"""Tests for audit API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key-for-unit-tests"
HEADERS = {"X-API-Key": TEST_API_KEY}


class TestAuditEndpoints:
    """Tests for the audit API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked startup checks and auth."""
        with patch("src.api.main.run_all_startup_checks", new_callable=AsyncMock):
            # Patch the settings object's api_key attribute
            import src.api.middleware.auth as auth_module

            original_api_key = auth_module.settings.api_key
            auth_module.settings.api_key = TEST_API_KEY

            from src.api.main import app

            client = TestClient(app)
            yield client

            # Restore original value
            auth_module.settings.api_key = original_api_key

    @pytest.fixture
    def mock_analyze(self):
        """Mock the analyze_dependencies function."""
        with patch(
            "src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies",
            new_callable=AsyncMock,
        ) as mock:
            yield mock

    def test_scan_endpoint_exists(self, client):
        """The /api/audit/scan endpoint should exist."""
        # Even without valid data, endpoint should respond (not 404)
        response = client.post("/api/audit/scan", json={}, headers=HEADERS)
        assert response.status_code != 404

    def test_scan_requires_project_path(self, client):
        """Scan endpoint should require project_path."""
        response = client.post("/api/audit/scan", json={}, headers=HEADERS)
        assert response.status_code == 422  # Validation error

    @patch("src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies", new_callable=AsyncMock)
    def test_scan_returns_vulnerabilities(self, mock_analyze, client, tmp_path):
        """Scan endpoint should return vulnerability information."""
        # Create a fake pom.xml
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("<project></project>")

        mock_analyze.return_value = """{
            "success": true,
            "vulnerabilities": [
                {
                    "cve": "CVE-2021-1234",
                    "severity": "high",
                    "dependency": "org.test:vulnerable:1.0",
                    "description": "Test vulnerability"
                }
            ],
            "current_dependencies": []
        }"""

        response = client.post(
            "/api/audit/scan",
            json={"project_path": str(tmp_path)},
            headers=HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_vulnerabilities"] == 1
        assert len(data["vulnerabilities"]) == 1
        assert data["vulnerabilities"][0]["cve"] == "CVE-2021-1234"

    @patch("src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies", new_callable=AsyncMock)
    def test_scan_filters_by_severity(self, mock_analyze, client, tmp_path):
        """Scan endpoint should filter by minimum severity."""
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("<project></project>")

        mock_analyze.return_value = """{
            "success": true,
            "vulnerabilities": [
                {"cve": "CVE-2021-0001", "severity": "low", "dependency": "a:b:1", "description": "Low"},
                {"cve": "CVE-2021-0002", "severity": "high", "dependency": "c:d:1", "description": "High"}
            ],
            "current_dependencies": []
        }"""

        response = client.post(
            "/api/audit/scan",
            json={"project_path": str(tmp_path), "severity": "high"},
            headers=HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        # Only high severity should be returned
        assert data["total_vulnerabilities"] == 1
        assert data["vulnerabilities"][0]["severity"] == "high"

    @patch("src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies", new_callable=AsyncMock)
    def test_scan_returns_summary(self, mock_analyze, client, tmp_path):
        """Scan endpoint should return severity summary."""
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("<project></project>")

        mock_analyze.return_value = """{
            "success": true,
            "vulnerabilities": [
                {"cve": "CVE-2021-0001", "severity": "critical", "dependency": "a:b:1", "description": ""},
                {"cve": "CVE-2021-0002", "severity": "high", "dependency": "c:d:1", "description": ""},
                {"cve": "CVE-2021-0003", "severity": "high", "dependency": "e:f:1", "description": ""}
            ],
            "current_dependencies": []
        }"""

        response = client.post(
            "/api/audit/scan",
            json={"project_path": str(tmp_path)},
            headers=HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["critical"] == 1
        assert data["summary"]["high"] == 2
        assert data["summary"]["medium"] == 0
        assert data["summary"]["low"] == 0

    def test_scan_invalid_path_returns_404(self, client):
        """Scan endpoint should return 404 for non-existent path."""
        response = client.post(
            "/api/audit/scan",
            json={"project_path": "/nonexistent/path/xyz123abc"},
            headers=HEADERS,
        )
        assert response.status_code == 404

    def test_scan_non_maven_project_returns_400(self, client, tmp_path):
        """Scan endpoint should return 400 for non-Maven project."""
        response = client.post(
            "/api/audit/scan",
            json={"project_path": str(tmp_path)},
            headers=HEADERS,
        )
        assert response.status_code == 400
        assert "pom.xml" in response.json()["detail"].lower()

    def test_report_endpoint_exists(self, client):
        """The /api/audit/report/{session_id} endpoint should exist."""
        response = client.get("/api/audit/report/test-session-id", headers=HEADERS)
        # Should return 404 for unknown session, not endpoint not found
        assert response.status_code == 404
        assert "session" in response.json()["detail"].lower()

    @patch("src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies", new_callable=AsyncMock)
    def test_report_returns_full_details(self, mock_analyze, client, tmp_path):
        """Report endpoint should return full audit details."""
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("<project></project>")

        mock_analyze.return_value = """{
            "success": true,
            "vulnerabilities": [
                {"cve": "CVE-2021-1234", "severity": "high", "dependency": "a:b:1", "description": "Test"}
            ],
            "current_dependencies": [
                {"groupId": "org.test", "artifactId": "lib", "version": "1.0.0", "scope": "compile"}
            ]
        }"""

        # First, create a scan to get a session ID
        scan_response = client.post(
            "/api/audit/scan",
            json={"project_path": str(tmp_path)},
            headers=HEADERS,
        )
        session_id = scan_response.json()["session_id"]

        # Then get the report
        report_response = client.get(f"/api/audit/report/{session_id}", headers=HEADERS)

        assert report_response.status_code == 200
        data = report_response.json()
        assert data["session_id"] == session_id
        assert len(data["vulnerabilities"]) == 1
        assert len(data["dependencies"]) == 1
        assert data["dependencies"][0]["groupId"] == "org.test"

    @patch("src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies", new_callable=AsyncMock)
    def test_report_html_returns_html(self, mock_analyze, client, tmp_path):
        """HTML report endpoint should return HTML content."""
        pom_file = tmp_path / "pom.xml"
        pom_file.write_text("<project></project>")

        mock_analyze.return_value = """{
            "success": true,
            "vulnerabilities": [],
            "current_dependencies": []
        }"""

        # Create a scan first
        scan_response = client.post(
            "/api/audit/scan",
            json={"project_path": str(tmp_path)},
            headers=HEADERS,
        )
        session_id = scan_response.json()["session_id"]

        # Get HTML report
        html_response = client.get(f"/api/audit/report/{session_id}/html", headers=HEADERS)

        assert html_response.status_code == 200
        assert "text/html" in html_response.headers["content-type"]
        assert "<html>" in html_response.text
        assert "Security Report" in html_response.text

    def test_report_html_unknown_session_returns_404(self, client):
        """HTML report for unknown session should return 404."""
        response = client.get("/api/audit/report/unknown-session/html", headers=HEADERS)
        assert response.status_code == 404


class TestAuditModels:
    """Tests for audit Pydantic models."""

    def test_audit_scan_request_model(self):
        """AuditScanRequest should have required fields."""
        from src.api.routers.audit import AuditScanRequest

        request = AuditScanRequest(project_path="/test/path")
        assert request.project_path == "/test/path"
        assert request.severity == "all"  # Default
        assert request.output_format == "json"  # Default

    def test_audit_scan_response_model(self):
        """AuditScanResponse should have required fields."""
        from src.api.routers.audit import AuditScanResponse

        response = AuditScanResponse(
            success=True,
            session_id="test-123",
            project_path="/test/path",
            total_vulnerabilities=0,
            vulnerabilities=[],
        )
        assert response.success is True
        assert response.session_id == "test-123"

    def test_vulnerability_info_model(self):
        """VulnerabilityInfo should have required fields."""
        from src.api.routers.audit import VulnerabilityInfo

        vuln = VulnerabilityInfo(
            cve="CVE-2021-1234",
            severity="high",
            dependency="org.test:lib:1.0",
        )
        assert vuln.cve == "CVE-2021-1234"
        assert vuln.severity == "high"
        assert vuln.description == ""  # Default
