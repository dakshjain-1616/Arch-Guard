"""Cyclomatic complexity detector."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from archguard.analyzers.base import ASTAnalyzer
from archguard.types import AnalysisResult, DetectorType, Severity, Violation

logger = logging.getLogger(__name__)


class CyclomaticComplexityDetector(ASTAnalyzer):
    """Detects functions/methods with high cyclomatic complexity."""

    # Default complexity thresholds
    DEFAULT_THRESHOLDS = {
        "low": 10,
        "medium": 20,
        "high": 30,
        "critical": 50,
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize cyclomatic complexity detector.
        
        Args:
            config: Configuration with optional thresholds:
                - low: Complexity threshold for low severity
                - medium: Complexity threshold for medium severity
                - high: Complexity threshold for high severity
                - critical: Complexity threshold for critical severity
        """
        super().__init__(config)

        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        self.thresholds.update(self.config.get("thresholds", {}))

        self.detector_type = DetectorType.CYCLOMATIC_COMPLEXITY

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze AST for cyclomatic complexity.
        
        Args:
            tree: AST tree.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._analyze_function(node, file_path, result)

    def _analyze_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze a single function for complexity.
        
        Args:
            node: Function AST node.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        func_name = node.name
        complexity = self._calculate_complexity(node)

        # Check against thresholds
        severity = None
        if complexity >= self.thresholds["critical"]:
            severity = Severity.CRITICAL
        elif complexity >= self.thresholds["high"]:
            severity = Severity.HIGH
        elif complexity >= self.thresholds["medium"]:
            severity = Severity.MEDIUM
        elif complexity >= self.thresholds["low"]:
            severity = Severity.LOW

        if severity:
            # Get complexity breakdown
            breakdown = self._get_complexity_breakdown(node)

            violation = Violation(
                detector_type=self.detector_type,
                severity=severity,
                message=(
                    f"Function '{func_name}' has high cyclomatic complexity: "
                    f"{complexity} (threshold: {self.thresholds['low']})"
                ),
                location=self.get_node_location(node, file_path),
                details={
                    "function_name": func_name,
                    "complexity": complexity,
                    "thresholds": self.thresholds,
                    "breakdown": breakdown,
                    "line_count": self._count_lines(node),
                },
                suggestion=self._generate_suggestion(func_name, complexity, breakdown),
            )
            result.add_violation(violation)

        # Store metrics
        result.metrics[f"func_{func_name}"] = {
            "complexity": complexity,
            "lines": self._count_lines(node),
        }

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function.
        
        Complexity starts at 1 and increments for each:
        - if/elif/else branch
        - for/while loop
        - except handler
        - with statement
        - boolean operator (and/or)
        - conditional expression
        - list/dict/set comprehension
        - generator expression
        
        Args:
            node: AST node (function or method).
            
        Returns:
            Cyclomatic complexity value.
        """
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Skip the function node itself
            if child is node:
                continue

            # Decision points
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
                # elif adds to complexity
                if isinstance(child, ast.If) and child.orelse:
                    # Check if it's an elif (orelse contains another If)
                    if len(child.orelse) == 1 and isinstance(child.orelse[0], ast.If):
                        complexity += 1

            elif isinstance(child, ast.ExceptHandler) or isinstance(child, ast.With):
                complexity += 1

            elif isinstance(child, ast.comprehension):
                # Each comprehension adds complexity
                complexity += 1
                # Each if in comprehension
                complexity += len(child.ifs)

            elif isinstance(child, ast.BoolOp):
                # Each boolean operator adds complexity
                complexity += len(child.values) - 1

            elif isinstance(child, ast.IfExp):
                # Conditional expression (ternary)
                complexity += 1

            elif isinstance(child, ast.Match):
                # Pattern matching (Python 3.10+)
                complexity += len(child.cases)

        return complexity

    def _get_complexity_breakdown(self, node: ast.AST) -> dict[str, int]:
        """Get detailed breakdown of complexity contributors.
        
        Args:
            node: AST node.
            
        Returns:
            Dictionary with counts of each complexity contributor.
        """
        breakdown = {
            "if": 0,
            "for": 0,
            "while": 0,
            "except": 0,
            "with": 0,
            "bool_op": 0,
            "comprehension": 0,
            "ternary": 0,
            "match": 0,
        }

        for child in ast.walk(node):
            if child is node:
                continue

            if isinstance(child, ast.If):
                breakdown["if"] += 1
            elif isinstance(child, ast.For):
                breakdown["for"] += 1
            elif isinstance(child, ast.While):
                breakdown["while"] += 1
            elif isinstance(child, ast.ExceptHandler):
                breakdown["except"] += 1
            elif isinstance(child, ast.With):
                breakdown["with"] += 1
            elif isinstance(child, ast.BoolOp):
                breakdown["bool_op"] += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                breakdown["comprehension"] += 1 + len(child.ifs)
            elif isinstance(child, ast.IfExp):
                breakdown["ternary"] += 1
            elif isinstance(child, ast.Match):
                breakdown["match"] += len(child.cases)

        return breakdown

    def _count_lines(self, node: ast.AST) -> int:
        """Count lines in a node.
        
        Args:
            node: AST node.
            
        Returns:
            Line count.
        """
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        return end_line - start_line + 1

    def _generate_suggestion(
        self,
        func_name: str,
        complexity: int,
        breakdown: dict[str, int]
    ) -> str:
        """Generate refactoring suggestion.
        
        Args:
            func_name: Name of the function.
            complexity: Complexity value.
            breakdown: Complexity breakdown.
            
        Returns:
            Suggestion string.
        """
        suggestions = []

        # Find main contributors
        main_contributors = [
            (k, v) for k, v in breakdown.items()
            if v > 0
        ]
        main_contributors.sort(key=lambda x: x[1], reverse=True)

        if main_contributors:
            top_contributor = main_contributors[0]

            if top_contributor[0] == "if" and top_contributor[1] > 5:
                suggestions.append(
                    f"Consider using a dictionary mapping or strategy pattern "
                    f"to replace the {top_contributor[1]} if-statements"
                )
            elif top_contributor[0] in ["for", "while"]:
                suggestions.append(
                    "Extract nested loops into separate functions"
                )
            elif top_contributor[0] == "bool_op":
                suggestions.append(
                    "Simplify complex boolean expressions by extracting them into named variables"
                )

        if complexity > 30:
            suggestions.append(
                f"Split '{func_name}' into smaller, focused functions"
            )

        suggestions.append(
            f"Target complexity: {self.thresholds['low']} or less"
        )

        return "; ".join(suggestions)
