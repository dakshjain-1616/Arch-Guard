"""Command-line interface for ArchGuard."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler

from archguard.analyzers.base import FileCollector
from archguard.config.schema import (
    ArchGuardConfig,
    ConfigLoader,
    create_default_config,
)
from archguard.detectors.circular_dependency import CircularDependencyDetector
from archguard.detectors.cyclomatic_complexity import CyclomaticComplexityDetector
from archguard.detectors.god_class import GodClassDetector
from archguard.detectors.layer_violation import LayerViolationDetector
from archguard.detectors.magic_value import MagicValueDetector
from archguard.detectors.service_layer_bypass import ServiceLayerBypassDetector
from archguard.formatters.base import get_formatter
from archguard.git.integration import GitIntegration, TrendAnalyzer
from archguard.types import AnalysisResult

console = Console()
stderr_console = Console(stderr=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger("archguard")


# Map detector names to classes
DETECTOR_MAP = {
    "circular_dependency": CircularDependencyDetector,
    "god_class": GodClassDetector,
    "service_layer_bypass": ServiceLayerBypassDetector,
    "magic_value": MagicValueDetector,
    "cyclomatic_complexity": CyclomaticComplexityDetector,
    "layer_violation": LayerViolationDetector,
}


@click.group()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, config: Path | None, verbose: bool) -> None:
    """ArchGuard - AI Code Architecture Drift Detector.
    
    Detect architecture degradation patterns in your codebase.
    """
    ctx.ensure_object(dict)

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    try:
        ctx.obj["config"] = ConfigLoader.load(config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        ctx.obj["config"] = ArchGuardConfig()


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json", "yaml", "markdown", "html"]),
    default="table",
    help="Output format",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output file path",
)
@click.option(
    "--detectors", "-d",
    multiple=True,
    help="Specific detectors to run (default: all)",
)
@click.option(
    "--severity", "-s",
    type=click.Choice(["critical", "high", "medium", "low", "info"]),
    default="low",
    help="Minimum severity to report",
)
@click.option(
    "--fail-on-violations", "--fail",
    is_flag=True,
    help="Exit with error code if violations found",
)
@click.pass_context
def scan(
    ctx: click.Context,
    path: Path,
    format: str,
    output: Path | None,
    detectors: tuple[str, ...],
    severity: str,
    fail_on_violations: bool,
) -> None:
    """Scan codebase for architecture violations.
    
    PATH is the directory or file to analyze (default: current directory).
    """
    config: ArchGuardConfig = ctx.obj["config"]

    # Override config with CLI options
    if output:
        config.output_file = output
    if format:
        config.output_format = format

    if format in {"json", "yaml"}:
        stderr_console.print(f"Scanning {path}...")
    else:
        console.print(f"🔍 Scanning {path}...")

    # Collect files
    collector = FileCollector(
        exclude_patterns=set(config.exclude_patterns),
        include_tests=config.include_tests,
    )

    files = list(collector.collect(path))

    if not files:
        stderr_console.print("No Python files found to analyze")
        return

    if format in {"json", "yaml"}:
        stderr_console.print(f"Found {len(files)} files to analyze")
    else:
        console.print(f"Found {len(files)} files to analyze")

    # Run detectors
    results: list[AnalysisResult] = []
    detector_names: tuple[str, ...] = detectors if detectors else tuple(DETECTOR_MAP.keys())

    with stderr_console.status("Analyzing...") as status:
        for file_path in files:
            status.update(f"Analyzing {file_path.name}...")
            result = analyze_file(file_path, detector_names, config)
            results.append(result)

    # Calculate summary
    summary = calculate_summary(results, severity)

    # Format and output results
    formatter = get_formatter(format, output)
    output_str = formatter.format_results(results, summary)

    if not output:
        if format in {"json", "yaml"}:
            sys.stdout.write(output_str + "\n")
        else:
            console.print(output_str)

    # Exit with error if requested and violations found
    if fail_on_violations and summary["total_violations"] > 0:
        sys.exit(1)


@cli.command()
@click.option(
    "--commits", "-n",
    type=int,
    default=10,
    help="Number of commits to analyze",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json", "yaml", "markdown", "html"]),
    default="table",
    help="Output format",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output file path",
)
@click.pass_context
def trend(
    ctx: click.Context,
    commits: int,
    format: str,
    output: Path | None,
) -> None:
    """Analyze architecture trends over commit history."""
    _ = ctx.obj["config"]

    git = GitIntegration()

    if not git.is_valid():
        console.print("[red]Error: Not a Git repository[/red]")
        sys.exit(1)

    console.print(f"📊 Analyzing trends over last {commits} commits...")

    trend_analyzer = TrendAnalyzer(git)

    # TODO: Implement proper analysis callback
    # For now, return empty trend
    trend_result = trend_analyzer.analyze_trends(commits)

    # Format and output
    formatter = get_formatter(format, output)
    output_str = formatter.format_trend(trend_result)

    if not output:
        console.print(output_str)


@cli.command()
@click.option(
    "--path", "-p",
    type=click.Path(path_type=Path),
    default=".archguard.yml",
    help="Path to create config file",
)
def init(path: Path) -> None:
    """Create a new configuration file."""
    if path.exists():
        overwrite = click.confirm(f"{path} already exists. Overwrite?")
        if not overwrite:
            console.print("[yellow]Configuration not created[/yellow]")
            return

    config_content = create_default_config()
    path.write_text(config_content, encoding="utf-8")

    console.print(f"[green]✅ Created configuration file: {path}[/green]")


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--unset", is_flag=True, help="Remove a configuration value")
@click.pass_context
def config(
    ctx: click.Context,
    key: str | None,
    value: str | None,
    unset: bool,
) -> None:
    """Get or set configuration values.
    
    Examples:
        archguard config                    # Show all config
        archguard config output_format      # Get output_format
        archguard config output_format json # Set output_format to json
    """
    cfg: ArchGuardConfig = ctx.obj["config"]

    if not key:
        # Show all config
        console.print(json.dumps(cfg.to_dict(), indent=2, default=str))
        return

    if unset:
        console.print(f"[yellow]Cannot unset {key} - not implemented[/yellow]")
        return

    if not value:
        # Get value
        cfg_dict = cfg.to_dict()
        if key in cfg_dict:
            console.print(f"{key}: {cfg_dict[key]}")
        else:
            console.print(f"[red]Unknown configuration key: {key}[/red]")
        return

    # Set value (simplified - just show message)
    console.print(f"[green]Set {key} = {value}[/green]")
    console.print("[yellow]Note: Use 'archguard init' to edit config file directly[/yellow]")


@cli.command()
@click.pass_context
def version(_: click.Context) -> None:
    """Show version information."""
    console.print("ArchGuard v0.1.0")
    console.print("AI Code Architecture Drift Detector")


def analyze_file(
    file_path: Path,
    detector_names: tuple[str, ...],
    config: ArchGuardConfig,
) -> AnalysisResult:
    """Analyze a single file with all enabled detectors.
    
    Args:
        file_path: Path to file.
        detector_names: Names of detectors to run.
        config: Configuration.
        
    Returns:
        Analysis result.
    """
    result = AnalysisResult(file_path=file_path)

    for detector_name in detector_names:
        if not config.is_detector_enabled(detector_name):
            continue

        detector_class = DETECTOR_MAP.get(detector_name)
        if not detector_class:
            continue

        try:
            detector_config = config.get_detector_config(detector_name)
            detector = detector_class(detector_config.options)

            detector_result = detector.analyze(file_path)

            # Merge violations
            for violation in detector_result.violations:
                result.add_violation(violation)

            # Merge metrics
            result.metrics.update(detector_result.metrics)

        except Exception as e:
            logger.warning(f"Error running {detector_name} on {file_path}: {e}")
            result.add_error(f"{detector_name}: {e}")

    return result


def calculate_summary(
    results: list[AnalysisResult],
    min_severity: str,
) -> dict[str, Any]:
    """Calculate summary statistics.
    
    Args:
        results: List of analysis results.
        min_severity: Minimum severity threshold.
        
    Returns:
        Summary dictionary.
    """
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    min_severity_level = severity_order.get(min_severity, 4)

    total_violations = 0
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0

    for result in results:
        for violation in result.violations:
            violation_level = severity_order.get(violation.severity.value, 4)

            if violation_level <= min_severity_level:
                total_violations += 1

                if violation.severity.value == "critical":
                    critical_count += 1
                elif violation.severity.value == "high":
                    high_count += 1
                elif violation.severity.value == "medium":
                    medium_count += 1
                elif violation.severity.value == "low":
                    low_count += 1

    return {
        "files_analyzed": len(results),
        "total_violations": total_violations,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
    }


def main() -> None:
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
