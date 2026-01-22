"""
Audit API router for security vulnerability scanning.

Provides endpoints for scanning Maven projects for security vulnerabilities
and generating audit reports.
"""

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.lib.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ============================================================================
# Pydantic Models (T073)
# ============================================================================


class VulnerabilityInfo(BaseModel):
    """Vulnerability information."""

    cve: str = Field(..., description="CVE identifier")
    severity: str = Field(..., description="Severity level (low, medium, high, critical)")
    dependency: str = Field(..., description="Affected dependency")
    description: str = Field("", description="Vulnerability description")


class DependencyInfo(BaseModel):
    """Dependency information for reports."""

    groupId: str
    artifactId: str
    version: str
    scope: str = "compile"


class AuditScanRequest(BaseModel):
    """Request model for audit scan."""

    project_path: str = Field(..., description="Path to the Maven project")
    severity: str = Field(
        "all", description="Minimum severity to report (all, low, medium, high, critical)"
    )
    output_format: str = Field("json", description="Output format (json, sarif)")


class AuditScanResponse(BaseModel):
    """Response model for audit scan."""

    success: bool
    session_id: str
    project_path: str
    total_vulnerabilities: int
    vulnerabilities: list[VulnerabilityInfo]
    summary: dict[str, int] = Field(default_factory=dict, description="Severity counts")
    error: str | None = None


class AuditReportResponse(BaseModel):
    """Response model for audit report."""

    session_id: str
    project_path: str
    generated_at: str
    total_vulnerabilities: int
    summary: dict[str, int]
    vulnerabilities: list[VulnerabilityInfo]
    dependencies: list[DependencyInfo]


# In-memory session storage for audit results
_audit_sessions: dict[str, dict[str, Any]] = {}


# ============================================================================
# Endpoints (T074-T076)
# ============================================================================


@router.post("/scan", response_model=AuditScanResponse)
async def scan_vulnerabilities(request: AuditScanRequest) -> AuditScanResponse:
    """
    Scan a Maven project for security vulnerabilities.

    Uses dependency analysis to identify known vulnerabilities (CVEs)
    in project dependencies.

    Args:
        request: Scan request parameters

    Returns:
        Scan results with vulnerability details
    """
    from pathlib import Path

    from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

    logger.info(
        "audit_scan_api",
        project_path=request.project_path,
        severity=request.severity,
    )

    # Validate project path
    project_dir = Path(request.project_path).resolve()
    if not project_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Project path not found: {request.project_path}"
        )

    pom_file = project_dir / "pom.xml"
    if not pom_file.exists():
        raise HTTPException(status_code=400, detail="Not a Maven project: pom.xml not found")

    try:
        # Run analysis
        result = await analyze_dependencies(
            str(project_dir), include_snapshots=False, check_vulnerabilities=True
        )
        analysis = json.loads(result)

        if not analysis.get("success"):
            return AuditScanResponse(
                success=False,
                session_id="",
                project_path=str(project_dir),
                total_vulnerabilities=0,
                vulnerabilities=[],
                error=analysis.get("error", "Scan failed"),
            )

        vulnerabilities = analysis.get("vulnerabilities", [])

        # Filter by severity if specified
        severity_order = ["low", "medium", "high", "critical"]
        if request.severity != "all" and request.severity in severity_order:
            min_idx = severity_order.index(request.severity)
            vulnerabilities = [
                v
                for v in vulnerabilities
                if severity_order.index(v.get("severity", "low").lower()) >= min_idx
            ]

        # Calculate summary
        summary = {
            "critical": sum(
                1 for v in vulnerabilities if v.get("severity", "").lower() == "critical"
            ),
            "high": sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "high"),
            "medium": sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "medium"),
            "low": sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "low"),
        }

        # Create session
        session_id = str(uuid4())

        # Store for later report retrieval
        _audit_sessions[session_id] = {
            "project_path": str(project_dir),
            "vulnerabilities": vulnerabilities,
            "dependencies": analysis.get("current_dependencies", []),
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
        }

        # Convert to response model
        vuln_models = [
            VulnerabilityInfo(
                cve=v.get("cve", ""),
                severity=v.get("severity", "unknown"),
                dependency=v.get("dependency", ""),
                description=v.get("description", ""),
            )
            for v in vulnerabilities
        ]

        return AuditScanResponse(
            success=True,
            session_id=session_id,
            project_path=str(project_dir),
            total_vulnerabilities=len(vulnerabilities),
            vulnerabilities=vuln_models,
            summary=summary,
        )

    except Exception as e:
        logger.error("audit_scan_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}") from e


@router.get("/report/{session_id}", response_model=AuditReportResponse)
async def get_audit_report(session_id: str) -> AuditReportResponse:
    """
    Get the audit report for a previous scan session.

    Args:
        session_id: ID from a previous scan

    Returns:
        Full audit report with vulnerabilities and dependencies
    """
    logger.info("audit_report_api", session_id=session_id)

    if session_id not in _audit_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session = _audit_sessions[session_id]

    # Convert vulnerabilities
    vuln_models = [
        VulnerabilityInfo(
            cve=v.get("cve", ""),
            severity=v.get("severity", "unknown"),
            dependency=v.get("dependency", ""),
            description=v.get("description", ""),
        )
        for v in session["vulnerabilities"]
    ]

    # Convert dependencies
    dep_models = [
        DependencyInfo(
            groupId=d.get("groupId", ""),
            artifactId=d.get("artifactId", ""),
            version=d.get("version", ""),
            scope=d.get("scope", "compile"),
        )
        for d in session["dependencies"]
    ]

    return AuditReportResponse(
        session_id=session_id,
        project_path=session["project_path"],
        generated_at=session["generated_at"],
        total_vulnerabilities=len(session["vulnerabilities"]),
        summary=session["summary"],
        vulnerabilities=vuln_models,
        dependencies=dep_models,
    )


@router.get("/report/{session_id}/html", response_class=HTMLResponse, response_model=None)
async def get_audit_report_html(session_id: str) -> HTMLResponse:
    """
    Get the audit report as an HTML page.

    Args:
        session_id: ID from a previous scan

    Returns:
        HTML formatted audit report
    """
    logger.info("audit_report_html_api", session_id=session_id)

    if session_id not in _audit_sessions:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session = _audit_sessions[session_id]

    html = _generate_html_report(
        project_path=session["project_path"],
        vulnerabilities=session["vulnerabilities"],
        dependencies=session["dependencies"],
    )

    return HTMLResponse(content=html)


def _generate_html_report(
    project_path: str, vulnerabilities: list[Any], dependencies: list[Any]
) -> str:
    """Generate an HTML security report."""
    critical = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "critical")
    high = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "high")
    medium = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "medium")
    low = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "low")

    vuln_rows = "\n".join(
        f"""
        <tr>
            <td>{v.get('cve', '')}</td>
            <td class="severity-{v.get('severity', '').lower()}">{v.get('severity', '')}</td>
            <td>{v.get('dependency', '')}</td>
            <td>{v.get('description', '')}</td>
        </tr>
        """
        for v in vulnerabilities
    )

    dep_rows = "\n".join(
        f"""
        <tr>
            <td>{d.get('groupId', '')}</td>
            <td>{d.get('artifactId', '')}</td>
            <td>{d.get('version', '')}</td>
            <td>{d.get('scope', '')}</td>
        </tr>
        """
        for d in dependencies
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Security Report - {project_path}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #333; }}
            .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
            .summary-card {{ padding: 20px; border-radius: 8px; min-width: 100px; text-align: center; }}
            .critical {{ background: #ff4444; color: white; }}
            .high {{ background: #ff8844; color: white; }}
            .medium {{ background: #ffcc00; color: black; }}
            .low {{ background: #88cc88; color: black; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background: #f5f5f5; }}
            .severity-critical {{ color: #ff4444; font-weight: bold; }}
            .severity-high {{ color: #ff8844; font-weight: bold; }}
            .severity-medium {{ color: #cc9900; }}
            .severity-low {{ color: #669966; }}
        </style>
    </head>
    <body>
        <h1>Security Report</h1>
        <p>Project: {project_path}</p>
        <p>Generated: {datetime.now().isoformat()}</p>

        <h2>Summary</h2>
        <div class="summary">
            <div class="summary-card critical">
                <h3>{critical}</h3>
                <p>Critical</p>
            </div>
            <div class="summary-card high">
                <h3>{high}</h3>
                <p>High</p>
            </div>
            <div class="summary-card medium">
                <h3>{medium}</h3>
                <p>Medium</p>
            </div>
            <div class="summary-card low">
                <h3>{low}</h3>
                <p>Low</p>
            </div>
        </div>

        <h2>Vulnerabilities ({len(vulnerabilities)})</h2>
        <table>
            <tr>
                <th>CVE</th>
                <th>Severity</th>
                <th>Dependency</th>
                <th>Description</th>
            </tr>
            {vuln_rows if vuln_rows else '<tr><td colspan="4">No vulnerabilities found</td></tr>'}
        </table>

        <h2>Dependencies ({len(dependencies)})</h2>
        <table>
            <tr>
                <th>Group ID</th>
                <th>Artifact ID</th>
                <th>Version</th>
                <th>Scope</th>
            </tr>
            {dep_rows if dep_rows else '<tr><td colspan="4">No dependencies</td></tr>'}
        </table>
    </body>
    </html>
    """
