"""Unit tests for ArchGuard types."""

from __future__ import annotations

from pathlib import Path

from archguard.types import (
    AnalysisResult,
    DetectorType,
    Location,
    ProjectSnapshot,
    Severity,
    TrendAnalysis,
    Violation,
)


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self) -> None:
        """Test severity enum values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"

    def test_severity_string_conversion(self) -> None:
        """Test severity string conversion."""
        assert str(Severity.CRITICAL) == "critical"
        assert str(Severity.HIGH) == "high"


class TestDetectorType:
    """Tests for DetectorType enum."""

    def test_detector_type_values(self) -> None:
        """Test detector type enum values."""
        assert DetectorType.CIRCULAR_DEPENDENCY.value == "circular_dependency"
        assert DetectorType.GOD_CLASS.value == "god_class"
        assert DetectorType.SERVICE_LAYER_BYPASS.value == "service_layer_bypass"
        assert DetectorType.MAGIC_VALUE.value == "magic_value"
        assert DetectorType.CYCLOMATIC_COMPLEXITY.value == "cyclomatic_complexity"
        assert DetectorType.LAYER_VIOLATION.value == "layer_violation"


class TestLocation:
    """Tests for Location dataclass."""

    def test_basic_location(self) -> None:
        """Test basic location creation."""
        loc = Location(
            file_path=Path("/test/file.py"),
            line_start=10,
        )

        assert loc.file_path == Path("/test/file.py")
        assert loc.line_start == 10
        assert loc.line_end == 10  # Should default to line_start

    def test_location_with_end(self) -> None:
        """Test location with explicit end."""
        loc = Location(
            file_path=Path("/test/file.py"),
            line_start=10,
            line_end=20,
            column_start=5,
            column_end=15,
        )

        assert loc.line_start == 10
        assert loc.line_end == 20
        assert loc.column_start == 5
        assert loc.column_end == 15

    def test_location_string_representation(self) -> None:
        """Test location string representation."""
        loc = Location(
            file_path=Path("/test/file.py"),
            line_start=10,
        )

        assert str(loc) == "/test/file.py:10"


class TestViolation:
    """Tests for Violation dataclass."""

    def test_basic_violation(self) -> None:
        """Test basic violation creation."""
        violation = Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="Class has too many methods",
            location=Location(file_path=Path("/test.py"), line_start=1),
        )

        assert violation.detector_type == DetectorType.GOD_CLASS
        assert violation.severity == Severity.HIGH
        assert violation.message == "Class has too many methods"

    def test_violation_to_dict(self) -> None:
        """Test violation to dictionary conversion."""
        violation = Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="Test message",
            location=Location(file_path=Path("/test.py"), line_start=10),
            details={"method_count": 25},
            suggestion="Refactor this class",
        )

        data = violation.to_dict()

        assert data["detector_type"] == "god_class"
        assert data["severity"] == "high"
        assert data["message"] == "Test message"
        assert data["line"] == 10
        assert data["details"] == {"method_count": 25}
        assert data["suggestion"] == "Refactor this class"


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_empty_result(self) -> None:
        """Test empty analysis result."""
        result = AnalysisResult(file_path=Path("/test.py"))

        assert result.file_path == Path("/test.py")
        assert len(result.violations) == 0
        assert len(result.errors) == 0
        assert result.metrics == {}

    def test_add_violation(self) -> None:
        """Test adding violations."""
        result = AnalysisResult(file_path=Path("/test.py"))

        violation = Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.MEDIUM,
            message="Test",
            location=Location(file_path=Path("/test.py"), line_start=1),
        )

        result.add_violation(violation)

        assert len(result.violations) == 1
        assert result.violations[0] == violation

    def test_add_error(self) -> None:
        """Test adding errors."""
        result = AnalysisResult(file_path=Path("/test.py"))

        result.add_error("Syntax error")

        assert len(result.errors) == 1
        assert result.errors[0] == "Syntax error"

    def test_result_to_dict(self) -> None:
        """Test result to dictionary conversion."""
        result = AnalysisResult(file_path=Path("/test.py"))

        violation = Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.MEDIUM,
            message="Test",
            location=Location(file_path=Path("/test.py"), line_start=1),
        )
        result.add_violation(violation)
        result.metrics["test_metric"] = 42

        data = result.to_dict()

        assert data["file_path"] == "/test.py"
        assert data["violation_count"] == 1
        assert len(data["violations"]) == 1
        assert data["metrics"]["test_metric"] == 42


class TestProjectSnapshot:
    """Tests for ProjectSnapshot dataclass."""

    def test_empty_snapshot(self) -> None:
        """Test empty snapshot."""
        snapshot = ProjectSnapshot(
            commit_hash="abc123",
            timestamp="2024-01-01T00:00:00",
        )

        assert snapshot.commit_hash == "abc123"
        assert snapshot.timestamp == "2024-01-01T00:00:00"
        assert len(snapshot.results) == 0
        assert snapshot.get_total_violations() == 0

    def test_get_total_violations(self) -> None:
        """Test getting total violations."""
        result1 = AnalysisResult(file_path=Path("/test1.py"))
        result1.add_violation(Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="Test",
            location=Location(file_path=Path("/test1.py"), line_start=1),
        ))

        result2 = AnalysisResult(file_path=Path("/test2.py"))
        result2.add_violation(Violation(
            detector_type=DetectorType.MAGIC_VALUE,
            severity=Severity.LOW,
            message="Test",
            location=Location(file_path=Path("/test2.py"), line_start=1),
        ))
        result2.add_violation(Violation(
            detector_type=DetectorType.MAGIC_VALUE,
            severity=Severity.LOW,
            message="Test 2",
            location=Location(file_path=Path("/test2.py"), line_start=2),
        ))

        snapshot = ProjectSnapshot(
            commit_hash="abc123",
            timestamp="2024-01-01T00:00:00",
            results=[result1, result2],
        )

        assert snapshot.get_total_violations() == 3

    def test_get_violations_by_severity(self) -> None:
        """Test getting violations grouped by severity."""
        result = AnalysisResult(file_path=Path("/test.py"))
        result.add_violation(Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="High",
            location=Location(file_path=Path("/test.py"), line_start=1),
        ))
        result.add_violation(Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="High 2",
            location=Location(file_path=Path("/test.py"), line_start=2),
        ))
        result.add_violation(Violation(
            detector_type=DetectorType.MAGIC_VALUE,
            severity=Severity.LOW,
            message="Low",
            location=Location(file_path=Path("/test.py"), line_start=3),
        ))

        snapshot = ProjectSnapshot(
            commit_hash="abc123",
            timestamp="2024-01-01T00:00:00",
            results=[result],
        )

        by_severity = snapshot.get_violations_by_severity()

        assert by_severity[Severity.HIGH] == 2
        assert by_severity[Severity.LOW] == 1

    def test_snapshot_to_dict(self) -> None:
        """Test snapshot to dictionary conversion."""
        snapshot = ProjectSnapshot(
            commit_hash="abc123",
            timestamp="2024-01-01T00:00:00",
            summary={"files": 10},
        )

        data = snapshot.to_dict()

        assert data["commit_hash"] == "abc123"
        assert data["timestamp"] == "2024-01-01T00:00:00"
        assert data["summary"]["files"] == 10
        assert data["total_violations"] == 0


class TestTrendAnalysis:
    """Tests for TrendAnalysis dataclass."""

    def test_empty_trend(self) -> None:
        """Test empty trend analysis."""
        trend = TrendAnalysis()

        assert len(trend.snapshots) == 0
        assert trend.trend_direction == "stable"
        assert trend.health_score == 0.0

    def test_calculate_trend_improving(self) -> None:
        """Test calculating improving trend."""
        # Create snapshots with decreasing violations
        snapshots = [
            ProjectSnapshot(
                commit_hash="abc1",
                timestamp="2024-01-01",
            ),
            ProjectSnapshot(
                commit_hash="abc2",
                timestamp="2024-01-02",
            ),
        ]

        # Add violations to first snapshot
        result1 = AnalysisResult(file_path=Path("/test.py"))
        result1.add_violation(Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="Test",
            location=Location(file_path=Path("/test.py"), line_start=1),
        ))
        snapshots[0].results.append(result1)

        # Second snapshot has no violations

        trend = TrendAnalysis(snapshots=snapshots)
        trend.calculate_trend()

        assert trend.trend_direction == "improving"
        assert trend.health_score > 0

    def test_calculate_trend_degrading(self) -> None:
        """Test calculating degrading trend."""
        snapshots = [
            ProjectSnapshot(
                commit_hash="abc1",
                timestamp="2024-01-01",
            ),
            ProjectSnapshot(
                commit_hash="abc2",
                timestamp="2024-01-02",
            ),
        ]

        # First snapshot has no violations

        # Second snapshot has violations
        result2 = AnalysisResult(file_path=Path("/test.py"))
        result2.add_violation(Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="Test",
            location=Location(file_path=Path("/test.py"), line_start=1),
        ))
        result2.add_violation(Violation(
            detector_type=DetectorType.GOD_CLASS,
            severity=Severity.HIGH,
            message="Test 2",
            location=Location(file_path=Path("/test.py"), line_start=2),
        ))
        snapshots[1].results.append(result2)

        trend = TrendAnalysis(snapshots=snapshots)
        trend.calculate_trend()

        assert trend.trend_direction == "degrading"

    def test_calculate_trend_stable(self) -> None:
        """Test calculating stable trend."""
        snapshots = [
            ProjectSnapshot(
                commit_hash="abc1",
                timestamp="2024-01-01",
            ),
            ProjectSnapshot(
                commit_hash="abc2",
                timestamp="2024-01-02",
            ),
        ]

        # Both snapshots have similar violations
        for snapshot in snapshots:
            result = AnalysisResult(file_path=Path("/test.py"))
            result.add_violation(Violation(
                detector_type=DetectorType.GOD_CLASS,
                severity=Severity.HIGH,
                message="Test",
                location=Location(file_path=Path("/test.py"), line_start=1),
            ))
            snapshot.results.append(result)

        trend = TrendAnalysis(snapshots=snapshots)
        trend.calculate_trend()

        assert trend.trend_direction == "stable"

    def test_trend_to_dict(self) -> None:
        """Test trend to dictionary conversion."""
        trend = TrendAnalysis(
            trend_direction="improving",
            health_score=85.5,
        )

        data = trend.to_dict()

        assert data["trend_direction"] == "improving"
        assert data["health_score"] == 85.5
        assert data["snapshot_count"] == 0
