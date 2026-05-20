"""Circular dependency detector."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from archguard.analyzers.base import ASTAnalyzer
from archguard.analyzers.dependency_graph import DependencyGraphBuilder
from archguard.types import AnalysisResult, DetectorType, Location, Severity, Violation

logger = logging.getLogger(__name__)


class CircularDependencyDetector(ASTAnalyzer):
    """Detects circular dependencies between modules."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize circular dependency detector.
        
        Args:
            config: Configuration with optional keys:
                - min_cycle_length: Minimum cycle length to report (default: 2)
                - max_cycles: Maximum cycles to report (default: 100)
        """
        super().__init__(config)
        self.min_cycle_length = self.config.get("min_cycle_length", 2)
        self.max_cycles = self.config.get("max_cycles", 100)
        self.detector_type = DetectorType.CIRCULAR_DEPENDENCY

    def analyze(self, file_path: Path, _content: str | None = None) -> AnalysisResult:
        """Analyze file for circular dependencies.
        
        Note: This detector needs project-wide analysis, so it builds
        the full dependency graph and finds cycles.
        
        Args:
            file_path: Path to analyze (used to find project root).
            content: Optional file content (not used for this detector).
            
        Returns:
            AnalysisResult with circular dependency violations.
        """
        result = AnalysisResult(file_path=file_path)

        # Find project root
        project_root = self._find_project_root(file_path)
        if not project_root:
            result.add_error(f"Could not find project root for: {file_path}")
            return result

        try:
            # Build dependency graph
            builder = DependencyGraphBuilder(project_root)
            builder.build_graph()

            # Find cycles
            cycles = builder.find_cycles()

            # Filter cycles by minimum length
            cycles = [c for c in cycles if len(c) >= self.min_cycle_length]

            # Limit number of cycles reported
            cycles = cycles[:self.max_cycles]

            # Create violations for each cycle
            for cycle in cycles:
                # Check if the analyzed file is part of this cycle
                current_module = builder._path_to_module(file_path)
                if current_module and current_module in cycle:
                    violation = self._create_violation(cycle, file_path, builder)
                    result.add_violation(violation)

            # Add metrics
            result.metrics["total_cycles_found"] = len(cycles)
            result.metrics["modules_in_cycles"] = len(set().union(*cycles)) if cycles else 0

        except Exception as e:
            logger.error(f"Error analyzing circular dependencies: {e}")
            result.add_error(f"Failed to analyze dependencies: {e}")

        return result

    def _find_project_root(self, file_path: Path) -> Path | None:
        """Find the project root directory.
        
        Args:
            file_path: Starting file path.
            
        Returns:
            Project root path or None.
        """
        path = file_path

        # Look for common project markers
        markers = ["pyproject.toml", "setup.py", "setup.cfg", ".git"]

        while path.parent != path:
            for marker in markers:
                if (path / marker).exists():
                    return path
            path = path.parent

        # Fallback to file's directory
        return file_path.parent if file_path.is_file() else file_path

    def _create_violation(
        self,
        cycle: list[str],
        file_path: Path,
        builder: DependencyGraphBuilder
    ) -> Violation:
        """Create a violation for a circular dependency.
        
        Args:
            cycle: List of modules in the cycle.
            file_path: File path for location.
            builder: Dependency graph builder.
            
        Returns:
            Violation object.
        """
        cycle_str = " → ".join(cycle) + " → " + cycle[0]

        # Determine severity based on cycle length
        if len(cycle) <= 2:
            severity = Severity.CRITICAL
        elif len(cycle) <= 4:
            severity = Severity.HIGH
        elif len(cycle) <= 6:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        # Get file paths for modules in cycle
        module_paths = []
        for module in cycle:
            mod_path = builder._module_to_path(module)
            if mod_path:
                module_paths.append(str(mod_path.relative_to(builder.project_root)))

        return Violation(
            detector_type=self.detector_type,
            severity=severity,
            message=f"Circular dependency detected: {cycle_str}",
            location=Location(file_path=file_path, line_start=1),
            details={
                "cycle": cycle,
                "cycle_length": len(cycle),
                "module_paths": module_paths,
            },
            suggestion=(
                "Break the circular dependency by: "
                "1) Extracting shared code into a separate module, "
                "2) Using dependency injection, or "
                "3) Moving one of the imports inside a function/method."
            ),
        )

    def _analyze_ast(self, tree: Any, file_path: Path, result: AnalysisResult) -> None:
        """Not used for circular dependency detection."""
        pass  # Circular dependencies are detected at module level
