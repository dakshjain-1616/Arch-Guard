"""Type definitions for ArchGuard."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Severity levels for architecture violations."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    def __str__(self) -> str:
        return self.value


class DetectorType(Enum):
    """Types of architecture detectors."""

    CIRCULAR_DEPENDENCY = "circular_dependency"
    GOD_CLASS = "god_class"
    SERVICE_LAYER_BYPASS = "service_layer_bypass"
    MAGIC_VALUE = "magic_value"
    CYCLOMATIC_COMPLEXITY = "cyclomatic_complexity"
    LAYER_VIOLATION = "layer_violation"


@dataclass
class Location:
    """Location of a code element in a file."""

    file_path: Path
    line_start: int
    line_end: int = field(default=0)
    column_start: int = field(default=0)
    column_end: int = field(default=0)

    def __post_init__(self) -> None:
        if self.line_end == 0:
            self.line_end = self.line_start

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line_start}"


@dataclass
class Violation:
    """Represents an architecture violation found by a detector."""

    detector_type: DetectorType
    severity: Severity
    message: str
    location: Location
    details: dict[str, Any] = field(default_factory=dict)
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert violation to dictionary."""
        return {
            "detector_type": self.detector_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "location": str(self.location),
            "file_path": str(self.location.file_path),
            "line": self.location.line_start,
            "details": self.details,
            "suggestion": self.suggestion,
        }


@dataclass
class AnalysisResult:
    """Result of analyzing a file or module."""

    file_path: Path
    violations: list[Violation] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add_violation(self, violation: Violation) -> None:
        """Add a violation to the result."""
        self.violations.append(violation)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "file_path": str(self.file_path),
            "violations": [v.to_dict() for v in self.violations],
            "metrics": self.metrics,
            "errors": self.errors,
            "violation_count": len(self.violations),
        }


@dataclass
class ProjectSnapshot:
    """Snapshot of project architecture at a point in time."""

    commit_hash: str
    timestamp: str
    results: list[AnalysisResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def get_total_violations(self) -> int:
        """Get total number of violations across all results."""
        return sum(len(r.violations) for r in self.results)

    def get_violations_by_severity(self) -> dict[Severity, int]:
        """Count violations by severity."""
        counts: dict[Severity, int] = {}
        for result in self.results:
            for violation in result.violations:
                counts[violation.severity] = counts.get(violation.severity, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "commit_hash": self.commit_hash,
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "total_violations": self.get_total_violations(),
            "violations_by_severity": {
                k.value: v for k, v in self.get_violations_by_severity().items()
            },
        }


@dataclass
class TrendAnalysis:
    """Analysis of architecture trends over time."""

    snapshots: list[ProjectSnapshot] = field(default_factory=list)
    trend_direction: str = "stable"  # "improving", "degrading", "stable"
    health_score: float = 0.0

    def calculate_trend(self) -> None:
        """Calculate trend direction based on snapshots."""
        if len(self.snapshots) < 2:
            return

        # Compare first and last snapshot
        first = self.snapshots[0].get_total_violations()
        last = self.snapshots[-1].get_total_violations()

        if last < first * 0.9:
            self.trend_direction = "improving"
        elif last > first * 1.1:
            self.trend_direction = "degrading"
        else:
            self.trend_direction = "stable"

        # Calculate health score (0-100)
        max_violations = max(s.get_total_violations() for s in self.snapshots) or 1
        self.health_score = max(0, 100 - (last / max_violations) * 50)

    def to_dict(self) -> dict[str, Any]:
        """Convert trend analysis to dictionary."""
        return {
            "trend_direction": self.trend_direction,
            "health_score": round(self.health_score, 2),
            "snapshot_count": len(self.snapshots),
            "snapshots": [s.to_dict() for s in self.snapshots],
        }


# Type aliases
PathLike = str | Path
ConfigDict = dict[str, Any]
