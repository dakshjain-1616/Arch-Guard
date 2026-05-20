"""Output formatters for ArchGuard."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from archguard.types import AnalysisResult, TrendAnalysis, Violation

logger = logging.getLogger(__name__)


class BaseFormatter(ABC):
    """Base class for output formatters."""

    def __init__(self, output_path: Path | None = None) -> None:
        """Initialize formatter.
        
        Args:
            output_path: Optional path to write output to.
        """
        self.output_path = output_path

    @abstractmethod
    def format_results(
        self,
        results: list[AnalysisResult],
        summary: dict[str, Any] | None = None
    ) -> str:
        """Format analysis results.
        
        Args:
            results: List of analysis results.
            summary: Optional summary data.
            
        Returns:
            Formatted output string.
        """
        pass

    @abstractmethod
    def format_trend(self, trend: TrendAnalysis) -> str:
        """Format trend analysis.
        
        Args:
            trend: Trend analysis.
            
        Returns:
            Formatted output string.
        """
        pass

    def write(self, content: str) -> None:
        """Write output to file if configured.
        
        Args:
            content: Content to write.
        """
        if self.output_path:
            self.output_path.write_text(content, encoding="utf-8")
            logger.info(f"Output written to {self.output_path}")


class TableFormatter(BaseFormatter):
    """Format output as a table using Rich."""

    def format_results(
        self,
        results: list[AnalysisResult],
        summary: dict[str, Any] | None = None
    ) -> str:
        """Format results as a table."""
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console(record=True)

        # Collect all violations
        all_violations: list[tuple[Violation, Path]] = []
        for result in results:
            for violation in result.violations:
                all_violations.append((violation, result.file_path))

        # Summary panel
        if summary:
            summary_text = f"""
Files Analyzed: {summary.get('files_analyzed', 0)}
Total Violations: {summary.get('total_violations', 0)}
Critical: {summary.get('critical_count', 0)}
High: {summary.get('high_count', 0)}
Medium: {summary.get('medium_count', 0)}
Low: {summary.get('low_count', 0)}
            """.strip()
            console.print(Panel(summary_text, title="ArchGuard Analysis Summary", border_style="blue"))

        if not all_violations:
            console.print(Panel("✅ No architecture violations found!", style="green"))
            output = console.export_text()
            self.write(output)
            return output

        # Violations table
        table = Table(
            title="Architecture Violations",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )

        table.add_column("Severity", style="cyan", width=10)
        table.add_column("Type", style="green", width=20)
        table.add_column("File", style="yellow", width=30)
        table.add_column("Line", style="blue", width=6)
        table.add_column("Message", style="white", width=50)

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_violations.sort(key=lambda x: severity_order.get(x[0].severity.value, 5))

        for violation, file_path in all_violations:
            severity_color = {
                "critical": "red",
                "high": "bright_red",
                "medium": "yellow",
                "low": "blue",
                "info": "dim",
            }.get(violation.severity.value, "white")

            table.add_row(
                f"[{severity_color}]{violation.severity.value}[/{severity_color}]",
                violation.detector_type.value,
                str(file_path),
                str(violation.location.line_start),
                violation.message[:47] + "..." if len(violation.message) > 50 else violation.message,
            )

        console.print(table)

        output = console.export_text()
        self.write(output)
        return output

    def format_trend(self, trend: TrendAnalysis) -> str:
        """Format trend analysis."""
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console(record=True)

        # Trend summary
        trend_color = {
            "improving": "green",
            "degrading": "red",
            "stable": "yellow",
        }.get(trend.trend_direction, "white")

        summary_text = f"""
Trend Direction: [{trend_color}]{trend.trend_direction}[/{trend_color}]
Health Score: {trend.health_score:.1f}/100
Snapshots Analyzed: {len(trend.snapshots)}
        """.strip()

        console.print(Panel(summary_text, title="Architecture Trend Analysis", border_style="blue"))

        # Snapshots table
        if trend.snapshots:
            table = Table(
                title="Commit History",
                box=box.ROUNDED,
                show_header=True,
            )

            table.add_column("Commit", style="cyan")
            table.add_column("Date", style="green")
            table.add_column("Violations", style="yellow")
            table.add_column("By Severity", style="white")

            for snapshot in trend.snapshots:
                severity_counts = snapshot.get_violations_by_severity()
                severity_str = ", ".join(
                    f"{k.value}:{v}" for k, v in severity_counts.items() if v > 0
                ) or "none"

                table.add_row(
                    snapshot.commit_hash[:8],
                    snapshot.timestamp[:10] if snapshot.timestamp else "",
                    str(snapshot.get_total_violations()),
                    severity_str,
                )

            console.print(table)

        output = console.export_text()
        self.write(output)
        return output


class JSONFormatter(BaseFormatter):
    """Format output as JSON."""

    def format_results(
        self,
        results: list[AnalysisResult],
        summary: dict[str, Any] | None = None
    ) -> str:
        """Format results as JSON."""
        data = {
            "summary": summary or {},
            "results": [r.to_dict() for r in results],
        }

        output = json.dumps(data, indent=2, default=str)
        self.write(output)
        return output

    def format_trend(self, trend: TrendAnalysis) -> str:
        """Format trend as JSON."""
        output = json.dumps(trend.to_dict(), indent=2, default=str)
        self.write(output)
        return output


class YAMLFormatter(BaseFormatter):
    """Format output as YAML."""

    def format_results(
        self,
        results: list[AnalysisResult],
        summary: dict[str, Any] | None = None
    ) -> str:
        """Format results as YAML."""
        data = {
            "summary": summary or {},
            "results": [r.to_dict() for r in results],
        }

        output = yaml.dump(data, default_flow_style=False, sort_keys=False)
        self.write(output)
        return output

    def format_trend(self, trend: TrendAnalysis) -> str:
        """Format trend as YAML."""
        output = yaml.dump(trend.to_dict(), default_flow_style=False, sort_keys=False)
        self.write(output)
        return output


class MarkdownFormatter(BaseFormatter):
    """Format output as Markdown."""

    def format_results(
        self,
        results: list[AnalysisResult],
        summary: dict[str, Any] | None = None
    ) -> str:
        """Format results as Markdown."""
        lines = ["# ArchGuard Analysis Report\n"]

        if summary:
            lines.append("## Summary\n")
            lines.append(f"- **Files Analyzed:** {summary.get('files_analyzed', 0)}")
            lines.append(f"- **Total Violations:** {summary.get('total_violations', 0)}")
            lines.append(f"- **Critical:** {summary.get('critical_count', 0)}")
            lines.append(f"- **High:** {summary.get('high_count', 0)}")
            lines.append(f"- **Medium:** {summary.get('medium_count', 0)}")
            lines.append(f"- **Low:** {summary.get('low_count', 0)}")
            lines.append("")

        # Collect all violations
        all_violations: list[tuple[Violation, Path]] = []
        for result in results:
            for violation in result.violations:
                all_violations.append((violation, result.file_path))

        if not all_violations:
            lines.append("✅ **No architecture violations found!**\n")
        else:
            lines.append("## Violations\n")
            lines.append("| Severity | Type | File | Line | Message |")
            lines.append("|----------|------|------|------|---------|")

            for violation, file_path in all_violations:
                lines.append(
                    f"| {violation.severity.value} | {violation.detector_type.value} | "
                    f"{file_path} | {violation.location.line_start} | {violation.message} |"
                )

        output = "\n".join(lines)
        self.write(output)
        return output

    def format_trend(self, trend: TrendAnalysis) -> str:
        """Format trend as Markdown."""
        lines = ["# Architecture Trend Analysis\n"]

        lines.append(f"- **Trend Direction:** {trend.trend_direction}")
        lines.append(f"- **Health Score:** {trend.health_score:.1f}/100")
        lines.append(f"- **Snapshots Analyzed:** {len(trend.snapshots)}")
        lines.append("")

        if trend.snapshots:
            lines.append("## Commit History\n")
            lines.append("| Commit | Date | Violations | Severity Breakdown |")
            lines.append("|--------|------|------------|-------------------|")

            for snapshot in trend.snapshots:
                severity_counts = snapshot.get_violations_by_severity()
                severity_str = ", ".join(
                    f"{k.value}:{v}" for k, v in severity_counts.items() if v > 0
                ) or "none"

                lines.append(
                    f"| {snapshot.commit_hash[:8]} | "
                    f"{snapshot.timestamp[:10] if snapshot.timestamp else ''} | "
                    f"{snapshot.get_total_violations()} | {severity_str} |"
                )

        output = "\n".join(lines)
        self.write(output)
        return output


class HTMLFormatter(BaseFormatter):
    """Format output as HTML."""

    def format_results(
        self,
        results: list[AnalysisResult],
        summary: dict[str, Any] | None = None
    ) -> str:
        """Format results as HTML."""
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>ArchGuard Analysis Report</title>",
            "<style>",
            "body { font-family: sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #4CAF50; color: white; }",
            ".critical { color: #d32f2f; font-weight: bold; }",
            ".high { color: #f57c00; }",
            ".medium { color: #fbc02d; }",
            ".low { color: #1976d2; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>ArchGuard Analysis Report</h1>",
        ]

        if summary:
            lines.append("<h2>Summary</h2>")
            lines.append("<ul>")
            lines.append(f"<li>Files Analyzed: {summary.get('files_analyzed', 0)}</li>")
            lines.append(f"<li>Total Violations: {summary.get('total_violations', 0)}</li>")
            lines.append(f"<li>Critical: {summary.get('critical_count', 0)}</li>")
            lines.append(f"<li>High: {summary.get('high_count', 0)}</li>")
            lines.append(f"<li>Medium: {summary.get('medium_count', 0)}</li>")
            lines.append(f"<li>Low: {summary.get('low_count', 0)}</li>")
            lines.append("</ul>")

        # Collect all violations
        all_violations: list[tuple[Violation, Path]] = []
        for result in results:
            for violation in result.violations:
                all_violations.append((violation, result.file_path))

        if not all_violations:
            lines.append("<p>✅ No architecture violations found!</p>")
        else:
            lines.append("<h2>Violations</h2>")
            lines.append("<table>")
            lines.append("<tr><th>Severity</th><th>Type</th><th>File</th><th>Line</th><th>Message</th></tr>")

            for violation, file_path in all_violations:
                severity_class = violation.severity.value
                lines.append(
                    f"<tr>"
                    f"<td class='{severity_class}'>{violation.severity.value}</td>"
                    f"<td>{violation.detector_type.value}</td>"
                    f"<td>{file_path}</td>"
                    f"<td>{violation.location.line_start}</td>"
                    f"<td>{violation.message}</td>"
                    f"</tr>"
                )

            lines.append("</table>")

        lines.extend(["</body>", "</html>"])

        output = "\n".join(lines)
        self.write(output)
        return output

    def format_trend(self, trend: TrendAnalysis) -> str:
        """Format trend as HTML."""
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Architecture Trend Analysis</title>",
            "</head>",
            "<body>",
            "<h1>Architecture Trend Analysis</h1>",
            f"<p>Trend Direction: {trend.trend_direction}</p>",
            f"<p>Health Score: {trend.health_score:.1f}/100</p>",
        ]

        if trend.snapshots:
            lines.append("<h2>Commit History</h2>")
            lines.append("<table>")
            lines.append("<tr><th>Commit</th><th>Date</th><th>Violations</th></tr>")

            for snapshot in trend.snapshots:
                lines.append(
                    f"<tr>"
                    f"<td>{snapshot.commit_hash[:8]}</td>"
                    f"<td>{snapshot.timestamp[:10] if snapshot.timestamp else ''}</td>"
                    f"<td>{snapshot.get_total_violations()}</td>"
                    f"</tr>"
                )

            lines.append("</table>")

        lines.extend(["</body>", "</html>"])

        output = "\n".join(lines)
        self.write(output)
        return output


def get_formatter(format_name: str, output_path: Path | None = None) -> BaseFormatter:
    """Get formatter by name.
    
    Args:
        format_name: Format name (table, json, yaml, markdown, html).
        output_path: Optional output path.
        
    Returns:
        Formatter instance.
    """
    formatters = {
        "table": TableFormatter,
        "json": JSONFormatter,
        "yaml": YAMLFormatter,
        "markdown": MarkdownFormatter,
        "html": HTMLFormatter,
    }

    formatter_class = formatters.get(format_name, TableFormatter)
    return formatter_class(output_path)
