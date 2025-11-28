"""
CLI commands for security audit operations.

Provides the 'boost audit' command for dependency security scanning.
"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.lib.logging import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="audit",
    help="Security audit commands for Maven projects",
    no_args_is_help=True,
)


@app.command("scan")
def scan_vulnerabilities(
    mode: str = typer.Option(
        "interactive",
        "--mode",
        help="Execution mode (interactive, autonomous, analysis_only, debug)",
    ),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Maven project",
    ),
    severity: str = typer.Option(
        "all",
        "--severity",
        "-s",
        help="Minimum severity to report (all, low, medium, high, critical)",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format (rich, json, sarif)",
    ),
    output_file: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path",
    ),
    fail_on: str = typer.Option(
        None,
        "--fail-on",
        help="Fail if vulnerabilities found at or above this severity",
    ),
) -> None:
    """
    Scan a Maven project for security vulnerabilities.

    Uses OWASP dependency-check and other sources to identify
    known vulnerabilities in project dependencies.
    """
    logger.info(
        "audit_scan_command",
        project_path=project_path,
        severity=severity,
        output_format=output_format,
    )

    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_dir}")
        raise typer.Exit(1)

    pom_file = project_dir / "pom.xml"
    if not pom_file.exists():
        console.print(f"[red]Error:[/red] Not a Maven project: pom.xml not found in {project_dir}")
        raise typer.Exit(1)

    async def _scan():
        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning for vulnerabilities...", total=None)

            result = await analyze_dependencies(
                str(project_dir), include_snapshots=False, check_vulnerabilities=True
            )

            progress.update(task, completed=True)

            return json.loads(result)

    analysis = asyncio.run(_scan())

    if not analysis.get("success"):
        console.print(f"[red]Error:[/red] {analysis.get('error', 'Scan failed')}")
        raise typer.Exit(1)

    vulnerabilities = analysis.get("vulnerabilities", [])

    # Filter by severity
    severity_order = ["low", "medium", "high", "critical"]
    if severity != "all" and severity in severity_order:
        min_idx = severity_order.index(severity)
        vulnerabilities = [
            v
            for v in vulnerabilities
            if severity_order.index(v.get("severity", "low").lower()) >= min_idx
        ]

    # Format output
    if output_format == "json":
        output = {
            "project_path": str(project_dir),
            "total_vulnerabilities": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
        }

        if output_file:
            with open(output_file, "w") as f:
                json.dump(output, f, indent=2)
            console.print(f"Results written to: {output_file}")
        else:
            console.print_json(json.dumps(output))

    elif output_format == "sarif":
        # SARIF format for integration with security tools
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "TestBoost",
                            "version": "0.1.0",
                            "informationUri": "https://github.com/testboost",
                        }
                    },
                    "results": [
                        {
                            "ruleId": v.get("cve", ""),
                            "message": {"text": v.get("description", "")},
                            "level": (
                                "error"
                                if v.get("severity", "").lower() in ["high", "critical"]
                                else "warning"
                            ),
                            "locations": [
                                {"physicalLocation": {"artifactLocation": {"uri": "pom.xml"}}}
                            ],
                        }
                        for v in vulnerabilities
                    ],
                }
            ],
        }

        if output_file:
            with open(output_file, "w") as f:
                json.dump(sarif, f, indent=2)
            console.print(f"SARIF report written to: {output_file}")
        else:
            console.print_json(json.dumps(sarif))

    else:
        # Rich formatted output
        if vulnerabilities:
            # Summary panel
            critical = sum(
                1 for v in vulnerabilities if v.get("severity", "").lower() == "critical"
            )
            high = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "high")
            medium = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "medium")
            low = sum(1 for v in vulnerabilities if v.get("severity", "").lower() == "low")

            summary = (
                f"Total Vulnerabilities: {len(vulnerabilities)}\n\n"
                f"[red]Critical: {critical}[/red]\n"
                f"[yellow]High: {high}[/yellow]\n"
                f"[blue]Medium: {medium}[/blue]\n"
                f"[dim]Low: {low}[/dim]"
            )

            console.print(Panel(summary, title="Security Scan Results"))

            # Detailed table
            table = Table(title="Vulnerabilities")
            table.add_column("CVE", style="red")
            table.add_column("Severity", style="yellow")
            table.add_column("Dependency", style="cyan")
            table.add_column("Description", max_width=50)

            for vuln in vulnerabilities:
                severity_style = {
                    "critical": "bold red",
                    "high": "red",
                    "medium": "yellow",
                    "low": "dim",
                }.get(vuln.get("severity", "").lower(), "")

                table.add_row(
                    vuln.get("cve", ""),
                    f"[{severity_style}]{vuln.get('severity', '')}[/{severity_style}]",
                    vuln.get("dependency", ""),
                    (
                        vuln.get("description", "")[:100] + "..."
                        if len(vuln.get("description", "")) > 100
                        else vuln.get("description", "")
                    ),
                )

            console.print(table)

        else:
            console.print(
                Panel(
                    "[green]No vulnerabilities found![/green]\n\n"
                    "Your dependencies appear to be secure.",
                    title="Security Scan Results",
                )
            )

    # Check fail condition
    if fail_on and fail_on in severity_order:
        fail_idx = severity_order.index(fail_on)
        failing_vulns = [
            v
            for v in vulnerabilities
            if severity_order.index(v.get("severity", "low").lower()) >= fail_idx
        ]

        if failing_vulns:
            console.print(
                f"\n[red]Found {len(failing_vulns)} vulnerabilities at or above '{fail_on}' severity[/red]"
            )
            raise typer.Exit(1)


@app.command("report")
def generate_report(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Maven project",
    ),
    output_file: str = typer.Option(
        "security-report.html",
        "--output",
        "-o",
        help="Output file path for the report",
    ),
    include_dependencies: bool = typer.Option(
        True,
        "--include-deps/--no-deps",
        help="Include full dependency tree in report",
    ),
) -> None:
    """
    Generate a comprehensive security report for a Maven project.

    Creates an HTML report with vulnerability details, recommendations,
    and remediation steps.
    """
    logger.info(
        "audit_report_command",
        project_path=project_path,
        output_file=output_file,
    )

    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_dir}")
        raise typer.Exit(1)

    async def _analyze():
        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating security report...", total=None)

            result = await analyze_dependencies(
                str(project_dir), include_snapshots=False, check_vulnerabilities=True
            )

            progress.update(task, completed=True)

            return json.loads(result)

    analysis = asyncio.run(_analyze())

    if not analysis.get("success"):
        console.print(f"[red]Error:[/red] {analysis.get('error', 'Analysis failed')}")
        raise typer.Exit(1)

    # Generate HTML report
    vulnerabilities = analysis.get("vulnerabilities", [])
    dependencies = analysis.get("current_dependencies", []) if include_dependencies else []

    html = _generate_html_report(
        project_path=str(project_dir), vulnerabilities=vulnerabilities, dependencies=dependencies
    )

    output_path = Path(output_file)
    output_path.write_text(html)

    console.print(f"[green]Security report generated:[/green] {output_path.absolute()}")


def _generate_html_report(project_path: str, vulnerabilities: list, dependencies: list) -> str:
    """Generate an HTML security report."""
    from datetime import datetime

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


if __name__ == "__main__":
    app()
