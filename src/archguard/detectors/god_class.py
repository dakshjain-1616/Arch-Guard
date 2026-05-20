"""God class detector - finds classes with too many responsibilities."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from archguard.analyzers.base import ASTAnalyzer
from archguard.types import AnalysisResult, DetectorType, Severity, Violation

logger = logging.getLogger(__name__)


class GodClassDetector(ASTAnalyzer):
    """Detects God Classes - classes with too many responsibilities."""

    # Default thresholds
    DEFAULT_MAX_METHODS = 20
    DEFAULT_MAX_ATTRIBUTES = 15
    DEFAULT_MAX_LINES = 500
    DEFAULT_MAX_INCOMING_DEPENDENCIES = 10

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize God Class detector.
        
        Args:
            config: Configuration with optional thresholds:
                - max_methods: Maximum methods per class
                - max_attributes: Maximum attributes per class
                - max_lines: Maximum lines per class
                - max_incoming_deps: Maximum incoming dependencies
        """
        super().__init__(config)
        self.max_methods = self.config.get("max_methods", self.DEFAULT_MAX_METHODS)
        self.max_attributes = self.config.get("max_attributes", self.DEFAULT_MAX_ATTRIBUTES)
        self.max_lines = self.config.get("max_lines", self.DEFAULT_MAX_LINES)
        self.max_incoming_deps = self.config.get(
            "max_incoming_deps",
            self.DEFAULT_MAX_INCOMING_DEPENDENCIES
        )
        self.detector_type = DetectorType.GOD_CLASS

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze AST for God Classes.
        
        Args:
            tree: AST tree.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._analyze_class(node, file_path, result)

    def _analyze_class(
        self,
        node: ast.ClassDef,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze a single class definition.
        
        Args:
            node: ClassDef AST node.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        class_name = node.name

        # Count methods
        methods = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        method_count = len(methods)

        # Count attributes (instance variables)
        attributes: set[str] = set()
        for method in methods:
            attributes.update(self._extract_attributes(method))
        attribute_count = len(attributes)

        # Count lines
        line_count = self._count_class_lines(node)

        # Calculate weighted score
        score = self._calculate_score(method_count, attribute_count, line_count)

        # Determine if this is a God Class
        violations = []

        if method_count > self.max_methods:
            violations.append(f"{method_count} methods (max: {self.max_methods})")

        if attribute_count > self.max_attributes:
            violations.append(f"{attribute_count} attributes (max: {self.max_attributes})")

        if line_count > self.max_lines:
            violations.append(f"{line_count} lines (max: {self.max_lines})")

        if violations:
            severity = self._determine_severity(
                method_count, attribute_count, line_count
            )

            violation = Violation(
                detector_type=self.detector_type,
                severity=severity,
                message=(
                    f"God Class detected: '{class_name}' has "
                    f"{', '.join(violations)}"
                ),
                location=self.get_node_location(node, file_path),
                details={
                    "class_name": class_name,
                    "method_count": method_count,
                    "attribute_count": attribute_count,
                    "line_count": line_count,
                    "score": score,
                    "thresholds": {
                        "max_methods": self.max_methods,
                        "max_attributes": self.max_attributes,
                        "max_lines": self.max_lines,
                    },
                },
                suggestion=self._generate_suggestion(
                    class_name, method_count, attribute_count
                ),
            )
            result.add_violation(violation)

        # Store metrics
        result.metrics[f"class_{class_name}"] = {
            "methods": method_count,
            "attributes": attribute_count,
            "lines": line_count,
            "score": score,
        }

    def _extract_attributes(
        self, method_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> set[str]:
        """Extract attribute assignments from a method.
        
        Args:
            method_node: Method AST node.
            
        Returns:
            Set of attribute names.
        """
        attributes: set[str] = set()

        for node in ast.walk(method_node):
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    attributes.add(node.attr)

        return attributes

    def _count_class_lines(self, node: ast.ClassDef) -> int:
        """Count lines in a class.
        
        Args:
            node: ClassDef node.
            
        Returns:
            Line count.
        """
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        return end_line - start_line + 1

    def _calculate_score(
        self,
        method_count: int,
        attribute_count: int,
        line_count: int
    ) -> float:
        """Calculate a weighted God Class score.
        
        Args:
            method_count: Number of methods.
            attribute_count: Number of attributes.
            line_count: Number of lines.
            
        Returns:
            Weighted score (higher = more likely God Class).
        """
        method_score = method_count / self.max_methods
        attr_score = attribute_count / self.max_attributes
        line_score = line_count / self.max_lines

        # Weight methods and attributes more heavily
        return (method_score * 0.4 + attr_score * 0.4 + line_score * 0.2) * 100

    def _determine_severity(
        self,
        method_count: int,
        attribute_count: int,
        line_count: int
    ) -> Severity:
        """Determine severity based on metrics.
        
        Args:
            method_count: Number of methods.
            attribute_count: Number of attributes.
            line_count: Number of lines.
            
        Returns:
            Severity level.
        """
        # Count how many thresholds are exceeded
        exceeded = 0
        if method_count > self.max_methods * 1.5:
            exceeded += 2
        elif method_count > self.max_methods:
            exceeded += 1

        if attribute_count > self.max_attributes * 1.5:
            exceeded += 2
        elif attribute_count > self.max_attributes:
            exceeded += 1

        if line_count > self.max_lines * 1.5:
            exceeded += 1

        if exceeded >= 4:
            return Severity.CRITICAL
        elif exceeded >= 3:
            return Severity.HIGH
        elif exceeded >= 2:
            return Severity.MEDIUM
        else:
            return Severity.LOW

    def _generate_suggestion(
        self,
        class_name: str,
        method_count: int,
        attribute_count: int
    ) -> str:
        """Generate refactoring suggestion.
        
        Args:
            class_name: Name of the class.
            method_count: Number of methods.
            attribute_count: Number of attributes.
            
        Returns:
            Suggestion string.
        """
        suggestions = []

        if method_count > self.max_methods:
            suggestions.append(
                f"Extract some of the {method_count} methods into separate classes "
                f"based on functionality (e.g., '{class_name}Service', '{class_name}Helper')"
            )

        if attribute_count > self.max_attributes:
            suggestions.append(
                "Group related attributes into value objects or data classes"
            )

        suggestions.append(
            "Consider applying the Single Responsibility Principle - "
            "a class should have only one reason to change"
        )

        return "; ".join(suggestions)
