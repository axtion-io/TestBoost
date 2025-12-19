"""CLI commands for test generation."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.progress import create_progress, is_windows
from src.lib.logging import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="tests",
    help="Test generation commands",
    no_args_is_help=True,
)


@app.command("generate")
def generate_tests(
    mode: str = typer.Option(
        "interactive",
        "--mode",
        help="Execution mode (interactive, autonomous, analysis_only, debug)",
    ),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    target: str = typer.Option(
        None,
        "--target",
        "-t",
        help="Specific class or package to generate tests for",
    ),
    mutation_score: float = typer.Option(
        80.0,
        "--mutation-score",
        "-m",
        help="Target mutation score percentage",
    ),
    include_integration: bool = typer.Option(
        True,
        "--integration/--no-integration",
        help="Generate integration tests",
    ),
    include_snapshot: bool = typer.Option(
        True,
        "--snapshot/--no-snapshot",
        help="Generate snapshot tests",
    ),
    output_dir: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for generated tests",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Analyze without generating tests",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """
    Generate tests for a Java project.

    This command analyzes the project structure, detects test conventions,
    and generates comprehensive tests targeting the specified mutation score.
    """
    logger.info(
        "generate_tests_command",
        project_path=project_path,
        target=target,
        mutation_score=mutation_score,
    )

    # Validate project path
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_path}")
        raise typer.Exit(1)

    # Check for Java project (support multi-module Maven projects)
    src_dir = project_dir / "src" / "main" / "java"
    has_java_sources = src_dir.exists()

    # Check for multi-module Maven structure
    if not has_java_sources and (project_dir / "pom.xml").exists():
        for subdir in project_dir.iterdir():
            if subdir.is_dir() and (subdir / "pom.xml").exists():
                module_src = subdir / "src" / "main" / "java"
                if module_src.exists():
                    has_java_sources = True
                    break

    if not has_java_sources:
        console.print("[red]Error:[/red] Not a Java project (no src/main/java found)")
        raise typer.Exit(1)

    console.print("\n[bold blue]TestBoost[/bold blue] - Test Generation")
    console.print(f"Project: {project_dir}")
    console.print(f"Target mutation score: {mutation_score}%\n")

    if dry_run:
        console.print("[yellow]Dry run mode - analyzing only[/yellow]\n")
        _run_analysis(project_dir, verbose)
        return

    # Run test generation workflow
    asyncio.run(
        _run_test_generation(
            project_dir,
            target,
            mutation_score,
            include_integration,
            include_snapshot,
            output_dir,
            verbose,
        )
    )


@app.command("analyze")
def analyze_project(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """
    Analyze a Java project for test generation.

    This command analyzes the project structure without generating tests,
    useful for understanding what tests would be generated.
    """
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_path}")
        raise typer.Exit(1)

    console.print("\n[bold blue]TestBoost[/bold blue] - Project Analysis")
    console.print(f"Project: {project_dir}\n")

    _run_analysis(project_dir, verbose)


@app.command("mutation")
def run_mutation(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    target_classes: str = typer.Option(
        None,
        "--classes",
        "-c",
        help="Target classes to mutate (glob pattern)",
    ),
    target_tests: str = typer.Option(
        None,
        "--tests",
        "-t",
        help="Target tests to run (glob pattern)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """
    Run mutation testing on a Java project.

    Uses PIT mutation testing to measure test effectiveness.
    """
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_path}")
        raise typer.Exit(1)

    console.print("\n[bold blue]TestBoost[/bold blue] - Mutation Testing")
    console.print(f"Project: {project_dir}\n")

    asyncio.run(_run_mutation_testing(project_dir, target_classes, target_tests, verbose))


@app.command("recommendations")
def show_recommendations(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    target_score: float = typer.Option(
        80.0,
        "--target",
        "-t",
        help="Target mutation score percentage",
    ),
    strategy: str = typer.Option(
        "balanced",
        "--strategy",
        "-s",
        help="Prioritization strategy (quick_wins, high_impact, balanced)",
    ),
) -> None:
    """
    Show test improvement recommendations.

    Analyzes mutation testing results and provides prioritized
    recommendations for improving test effectiveness.
    """
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_path}")
        raise typer.Exit(1)

    console.print("\n[bold blue]TestBoost[/bold blue] - Test Improvement Recommendations")
    console.print(f"Project: {project_dir}")
    console.print(f"Strategy: {strategy}\n")

    asyncio.run(_show_recommendations(project_dir, target_score, strategy))


@app.command("impact")
def analyze_impact(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Save report to file (default: stdout)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show progress and debug info",
    ),
    chunk_size: int = typer.Option(
        500,
        "--chunk-size",
        help="Max lines per chunk for large diffs",
    ),
) -> None:
    """
    Analyze impact of uncommitted changes.

    Detects uncommitted changes in your working directory,
    classifies each change by category and risk level,
    and generates an impact report with test requirements.

    Exit codes:
      0 - Success, all impacts covered or no business-critical uncovered
      1 - Business-critical impacts have no tests (for CI enforcement)
    """
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_path}")
        raise typer.Exit(1)

    # Check for git repo
    if not (project_dir / ".git").exists():
        console.print(f"[red]Error:[/red] Not a git repository: {project_path}")
        raise typer.Exit(1)

    if verbose:
        console.print("\n[bold blue]TestBoost[/bold blue] - Impact Analysis")
        console.print(f"Project: {project_dir}\n")

    asyncio.run(_run_impact_analysis(project_dir, output, verbose, chunk_size))


def _run_analysis(project_dir: Path, verbose: bool) -> None:
    """Run project analysis."""
    import json

    async def analyze() -> None:
        from src.mcp_servers.test_generator.tools.analyze import analyze_project_context
        from src.mcp_servers.test_generator.tools.conventions import detect_test_conventions

        with create_progress(console) as progress:



            # Analyze project
            task = progress.add_task("Analyzing project structure...", total=None)
            result = await analyze_project_context(str(project_dir))
            context = json.loads(result)
            progress.remove_task(task)

            if not context.get("success"):
                console.print(f"[red]Analysis failed:[/red] {context.get('error')}")
                return

            # Detect conventions
            task = progress.add_task("Detecting test conventions...", total=None)
            conv_result = await detect_test_conventions(str(project_dir))
            conventions = json.loads(conv_result)
            progress.remove_task(task)

        # Display results
        console.print("[bold green]Analysis Complete[/bold green]\n")

        # Project info table
        table = Table(title="Project Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Project Type", context.get("project_type", "unknown"))
        table.add_row("Build System", context.get("build_system", "unknown"))
        table.add_row("Java Version", context.get("java_version", "unknown"))
        table.add_row("Frameworks", ", ".join(context.get("frameworks", [])) or "None")
        table.add_row("Test Frameworks", ", ".join(context.get("test_frameworks", [])) or "None")

        src_structure = context.get("source_structure", {})
        table.add_row("Source Classes", str(src_structure.get("class_count", 0)))

        test_structure = context.get("test_structure", {})
        table.add_row("Existing Tests", str(test_structure.get("test_count", 0)))

        console.print(table)
        console.print()

        # Conventions info
        if conventions.get("success"):
            console.print("[bold]Detected Conventions:[/bold]")
            naming = conventions.get("naming", {})
            console.print(f"  Naming pattern: {naming.get('dominant_pattern', 'unknown')}")

            assertions = conventions.get("assertions", {})
            console.print(f"  Assertion style: {assertions.get('dominant_style', 'unknown')}")

            mocking = conventions.get("mocking", {})
            console.print(f"  Uses Mockito: {mocking.get('uses_mockito', False)}")

        if verbose:
            console.print("\n[bold]Packages:[/bold]")
            for pkg in src_structure.get("packages", [])[:10]:
                console.print(f"  - {pkg}")

    asyncio.run(analyze())


async def _run_test_generation(
    project_dir: Path,
    target: str | None,
    mutation_score: float,
    include_integration: bool,
    include_snapshot: bool,
    output_dir: str | None,
    verbose: bool,
) -> None:
    """Run test generation workflow with LLM agent (T063)."""
    from src.db import SessionLocal
    from src.db.repository import SessionRepository
    from src.workflows.test_generation_agent import run_test_generation_with_agent

    # Show agent workflow notice
    console.print("[yellow]Using LLM-powered test generation agent[/yellow]")
    console.print("[dim]LangSmith tracing enabled if LANGSMITH_TRACING=true[/dim]\n")

    with create_progress(console) as progress:



        task = progress.add_task("Running test generation workflow with agent...", total=None)

        try:
            # Create session in database
            async with SessionLocal() as db_session:
                session_repo = SessionRepository(db_session)
                session = await session_repo.create(
                    session_type="test_generation",
                    status="in_progress",
                    mode="autonomous",
                    project_path=str(project_dir),
                    config={"target_coverage": mutation_score},
                )
                session_id = session.id

                # Run agent-based workflow (T062)
                result = await run_test_generation_with_agent(
                    session_id=session_id,
                    project_path=str(project_dir),
                    db_session=db_session,
                    coverage_target=mutation_score,
                )

                # Update session status
                await session_repo.update(session_id, status="completed")
                await db_session.commit()

            progress.remove_task(task)

            # Display results
            if not result.get("success"):
                console.print("\n[red]Test generation failed[/red]")
                raise typer.Exit(1)

            console.print("\n[bold green]Test Generation Complete[/bold green]\n")

            # Results table
            table = Table(title="Generation Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            metrics = result.get("metrics", {})
            generated_tests = result.get("generated_tests", [])

            table.add_row("Tests Generated", str(metrics.get("tests_generated", 0)))
            table.add_row("Compilation Success", str(metrics.get("compilation_success", False)))
            table.add_row("Coverage Target", f"{metrics.get('coverage_target', mutation_score)}%")
            table.add_row("Duration", f"{metrics.get('duration_seconds', 0)}s")
            table.add_row("Agent", result.get("agent_name", "unknown"))

            console.print(table)

            # Show generated test files
            if generated_tests:
                console.print("\n[bold]Generated Test Files:[/bold]")
                # Use ASCII characters on Windows to avoid cp1252 encoding issues
                check_mark = "[green]OK[/green]" if is_windows() else "[green]✓[/green]"
                x_mark = "[red]FAIL[/red]" if is_windows() else "[red]✗[/red]"
                for test in generated_tests:
                    status = check_mark if test.get("compiles") else x_mark
                    console.print(f"  {status} {test.get('path', 'unknown')}")
                    if test.get("correction_attempts", 0) > 0:
                        console.print(
                            f"    [dim]Auto-corrected after {test['correction_attempts']} attempts[/dim]"
                        )

            console.print("\n[bold]Next Steps:[/bold]")
            console.print("1. Review generated tests in src/test/java")
            console.print("2. Run test suite: mvn test")
            console.print("3. Check LangSmith traces for agent reasoning")
            console.print("4. Commit passing tests")

        except Exception as e:
            progress.remove_task(task)
            console.print(f"\n[red]Error:[/red] {str(e)}")
            raise typer.Exit(1) from None


async def _run_mutation_testing(
    project_dir: Path, target_classes: str | None, target_tests: str | None, verbose: bool
) -> None:
    """Run mutation testing."""
    import json

    from src.mcp_servers.test_generator.tools.mutation import run_mutation_testing

    with create_progress(console) as progress:



        task = progress.add_task("Running mutation testing (this may take a while)...", total=None)

        classes = [target_classes] if target_classes else None
        tests = [target_tests] if target_tests else None

        result = await run_mutation_testing(
            str(project_dir), target_classes=classes, target_tests=tests
        )

        progress.remove_task(task)

        data = json.loads(result)

        if not data.get("success"):
            console.print(f"\n[red]Mutation testing failed:[/red] {data.get('error')}")
            raise typer.Exit(1)

        console.print("\n[bold green]Mutation Testing Complete[/bold green]\n")

        # Results table
        table = Table(title="Mutation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        mutations = data.get("mutations", {})
        table.add_row("Total Mutants", str(mutations.get("total", 0)))
        table.add_row("Killed", str(mutations.get("killed", 0)))
        table.add_row("Survived", str(mutations.get("survived", 0)))
        table.add_row("No Coverage", str(mutations.get("no_coverage", 0)))
        table.add_row("Mutation Score", f"{data.get('mutation_score', 0)}%")

        console.print(table)

        # Show classes needing attention
        by_class = data.get("by_class", [])
        if by_class and verbose:
            console.print("\n[bold]Classes with Low Scores:[/bold]")
            for cls in by_class[:5]:
                if cls.get("score", 100) < 80:
                    console.print(f"  - {cls['class']}: {cls['score']}%")


async def _show_recommendations(project_dir: Path, target_score: float, strategy: str) -> None:
    """Show test improvement recommendations."""
    import json

    from src.mcp_servers.pit_recommendations.tools.prioritize import prioritize_test_efforts
    from src.mcp_servers.pit_recommendations.tools.recommend import recommend_test_improvements

    with create_progress(console) as progress:



        task = progress.add_task("Analyzing mutation results...", total=None)

        # Get recommendations
        rec_result = await recommend_test_improvements(str(project_dir), target_score=target_score)
        rec_data = json.loads(rec_result)

        if not rec_data.get("success"):
            progress.remove_task(task)
            console.print(f"\n[red]Analysis failed:[/red] {rec_data.get('error')}")
            raise typer.Exit(1)

        # Prioritize
        pri_result = await prioritize_test_efforts(
            str(project_dir), recommendations=rec_data.get("recommendations"), strategy=strategy
        )
        pri_data = json.loads(pri_result)

        progress.remove_task(task)

    console.print("\n[bold green]Recommendations[/bold green]\n")

    # Summary
    console.print(f"Current Score: {rec_data.get('current_score', 0)}%")
    console.print(f"Target Score: {target_score}%")
    console.print(f"Gap: {rec_data.get('score_gap', 0):.1f}%\n")

    # Recommendations table
    recommendations = pri_data.get("prioritized", [])[:10]

    if recommendations:
        table = Table(title="Prioritized Recommendations")
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Priority", style="yellow", width=10)
        table.add_column("Recommendation", style="white")
        table.add_column("Impact", style="green", width=8)

        for rec in recommendations:
            table.add_row(
                str(rec.get("rank", "")),
                rec.get("priority", ""),
                rec.get("title", ""),
                rec.get("impact", ""),
            )

        console.print(table)
    else:
        console.print("[yellow]No recommendations available.[/yellow]")
        console.print("Run mutation testing first: testboost tests mutation")


async def _run_impact_analysis(
    project_dir: Path,
    output: str | None,
    verbose: bool,
    chunk_size: int,
) -> None:
    """Run impact analysis workflow (T029-T032)."""
    import json

    from src.workflows.impact_analysis import run_impact_analysis

    def progress_callback(current: int, total: int, message: str) -> None:
        if verbose:
            console.print(f"[dim][{current}/{total}] {message}[/dim]")

    try:
        if verbose:
            with create_progress(console) as progress:
                task = progress.add_task("Analyzing uncommitted changes...", total=None)
                report = await run_impact_analysis(
                    str(project_dir),
                    progress_callback=progress_callback if verbose else None,
                )
                progress.remove_task(task)
        else:
            report = await run_impact_analysis(str(project_dir))

        # Convert to JSON
        report_dict = report.to_dict()
        json_output = json.dumps(report_dict, indent=2)

        # Output to file or stdout (T030)
        if output:
            output_path = Path(output)
            output_path.write_text(json_output, encoding="utf-8")
            if verbose:
                console.print(f"[green]Report saved to {output}[/green]")
        else:
            # Output to stdout (for piping)
            print(json_output)

        # Display summary if verbose
        if verbose:
            console.print("\n[bold green]Impact Analysis Complete[/bold green]\n")

            summary = report.summary
            table = Table(title="Impact Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Impacts", str(summary["total_impacts"]))
            table.add_row("Business Critical", str(summary["business_critical"]))
            table.add_row("Non-Critical", str(summary["non_critical"]))
            table.add_row("Tests to Generate", str(summary["tests_to_generate"]))
            table.add_row("Processing Time", f"{report.processing_time_seconds:.2f}s")

            console.print(table)

            # Show impacts
            if report.impacts:
                console.print("\n[bold]Impacts Found:[/bold]")
                critical_mark = "[red]CRIT[/red]" if is_windows() else "[red]!![/red]"
                normal_mark = "[dim]--[/dim]"

                for impact in report.impacts:
                    risk_indicator = (
                        critical_mark
                        if impact.risk_level.value == "business_critical"
                        else normal_mark
                    )
                    console.print(
                        f"  {risk_indicator} {impact.id}: {impact.change_summary}"
                    )

        # Exit code logic (T032)
        if report.has_uncovered_critical_impacts():
            if verbose:
                console.print(
                    "\n[yellow]Warning: Business-critical impacts detected[/yellow]"
                )
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        logger.exception("impact_analysis_failed", error=str(e))
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
