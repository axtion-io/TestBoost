"""CLI commands for test generation."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, TextColumn
from rich.table import Table
from src.cli.progress import create_progress

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

    # Check for Java project
    src_dir = project_dir / "src" / "main" / "java"
    if not src_dir.exists():
        console.print("[red]Error:[/red] Not a Java project (src/main/java not found)")
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


def _run_analysis(project_dir: Path, verbose: bool) -> None:
    """Run project analysis."""
    import json

    async def analyze():
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
    """Run test generation workflow."""
    from src.workflows.test_generation import run_test_generation

    with create_progress(console) as progress:
        
        
    
        task = progress.add_task("Running test generation workflow...", total=None)

        try:
            final_state = await run_test_generation(
                str(project_dir), target_mutation_score=mutation_score
            )

            progress.remove_task(task)

            # Display results
            if final_state.errors:
                console.print(f"\n[red]Test generation failed:[/red] {final_state.errors[0]}")
                raise typer.Exit(1)

            console.print("\n[bold green]Test Generation Complete[/bold green]\n")

            # Results table
            table = Table(title="Generation Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Unit Tests Generated", str(len(final_state.generated_unit_tests)))
            table.add_row(
                "Integration Tests Generated", str(len(final_state.generated_integration_tests))
            )
            table.add_row(
                "Snapshot Tests Generated", str(len(final_state.generated_snapshot_tests))
            )
            table.add_row("Killer Tests Generated", str(len(final_state.killer_tests_generated)))
            table.add_row("Mutation Score", f"{final_state.mutation_score}%")
            table.add_row("Target Score", f"{mutation_score}%")

            console.print(table)

            if final_state.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in final_state.warnings:
                    console.print(f"  - {warning}")

            console.print("\n[bold]Next Steps:[/bold]")
            console.print("1. Review generated tests in src/test/java")
            console.print("2. Run test suite: mvn test")
            console.print("3. Commit passing tests")

        except Exception as e:
            progress.remove_task(task)
            console.print(f"\n[red]Error:[/red] {str(e)}")
            raise typer.Exit(1)


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


if __name__ == "__main__":
    app()
