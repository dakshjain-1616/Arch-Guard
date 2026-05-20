"""Magic value detector - finds hardcoded literals that should be constants."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from archguard.analyzers.base import ASTAnalyzer
from archguard.types import AnalysisResult, DetectorType, Severity, Violation

logger = logging.getLogger(__name__)


class MagicValueDetector(ASTAnalyzer):
    """Detects magic numbers and strings that should be named constants."""

    # Default allowed values (common, self-explanatory values)
    DEFAULT_ALLOWED_NUMBERS: set[int | float] = {
        0, 1, -1, -1.0, 2, 100, 0.1, 0.01
    }

    DEFAULT_ALLOWED_STRINGS: set[str] = {
        "", " ", ",", ".", "-", "_", ":", ";", "/", "\\",
        "true", "false", "True", "False", "yes", "no",
        "localhost", "utf-8", "utf8", "ascii", "json", "xml",
    }

    # Patterns that are typically OK
    DEFAULT_EXCLUDED_PATTERNS: list[str] = [
        r"^\d{4}-\d{2}-\d{2}$",  # Dates
        r"^\d{2}:\d{2}:\d{2}$",  # Times
        r"^v?\d+\.\d+\.\d+",      # Version strings
        r"^#[0-9a-fA-F]{6}$",      # Hex colors
    ]

    # Contexts where magic values are OK
    DEFAULT_ALLOWED_CONTEXTS: list[str] = [
        "test_", "_test", "mock", "fake", "example", "sample",
        "fixture", "stub",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize magic value detector.
        
        Args:
            config: Configuration with optional settings:
                - allowed_numbers: Set of allowed numeric literals
                - allowed_strings: Set of allowed string literals
                - excluded_patterns: Regex patterns to exclude
                - min_string_length: Minimum string length to flag
                - max_string_length: Maximum string length to check
        """
        super().__init__(config)

        self.allowed_numbers = set(self.config.get("allowed_numbers", self.DEFAULT_ALLOWED_NUMBERS))
        self.allowed_strings = set(self.config.get("allowed_strings", self.DEFAULT_ALLOWED_STRINGS))

        patterns = self.config.get("excluded_patterns", self.DEFAULT_EXCLUDED_PATTERNS)
        self.excluded_patterns = [re.compile(p) for p in patterns]

        self.allowed_contexts = self.config.get("allowed_contexts", self.DEFAULT_ALLOWED_CONTEXTS)
        self.min_string_length = self.config.get("min_string_length", 3)
        self.max_string_length = self.config.get("max_string_length", 100)

        self.detector_type = DetectorType.MAGIC_VALUE

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze AST for magic values.
        
        Args:
            tree: AST tree.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        # Skip test files based on context
        if self._is_test_context(file_path):
            return

        for node in ast.walk(tree):
            # Check numeric literals
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    self._check_numeric_literal(node, file_path, result)
                elif isinstance(node.value, str):
                    self._check_string_literal(node, file_path, result)

            # Also check old-style Num and Str nodes (Python < 3.8)
            elif isinstance(node, ast.Num):
                self._check_numeric_literal(node, file_path, result)
            elif isinstance(node, ast.Str):
                self._check_string_literal(node, file_path, result)

    def _is_test_context(self, file_path: Path) -> bool:
        """Check if file is in a test context.
        
        Args:
            file_path: Path to check.
            
        Returns:
            True if test context.
        """
        stem = file_path.stem.lower()
        parent_names = [part.lower() for part in file_path.parents[0].parts]
        return stem.startswith("test_") or stem.endswith("_test") or "tests" in parent_names

    def _check_numeric_literal(
        self,
        node: ast.Constant | ast.Num,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Check if a numeric literal is a magic value.
        
        Args:
            node: AST node.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        value = node.value if isinstance(node, ast.Constant) else node.n
        if not isinstance(value, (int, float)):
            return

        # Skip allowed values
        if value in self.allowed_numbers:
            return

        # Skip if in allowed context (e.g., index access)
        if self._is_allowed_numeric_context(node):
            return

        # Determine severity based on value
        severity = self._determine_numeric_severity(value)

        violation = Violation(
            detector_type=self.detector_type,
            severity=severity,
            message=f"Magic number detected: {value:.2f}" if isinstance(value, float) else f"Magic number detected: {value}",
            location=self.get_node_location(node, file_path),
            details={
                "value": value,
                "value_type": type(value).__name__,
                "context": self._get_numeric_context(node),
            },
            suggestion=(
                f"Extract '{value}' into a named constant with a descriptive name, "
                f"e.g., MAX_RETRY_COUNT = {value} or TIMEOUT_SECONDS = {value}"
            ),
        )
        result.add_violation(violation)

    def _check_string_literal(
        self,
        node: ast.Constant | ast.Str,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Check if a string literal is a magic value.
        
        Args:
            node: AST node.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        value = node.value if isinstance(node, ast.Constant) else node.s

        # Skip non-string values
        if not isinstance(value, str):
            return

        # Skip allowed strings
        if value.lower() in {s.lower() for s in self.allowed_strings}:
            return

        # Skip based on length
        if len(value) < self.min_string_length or len(value) > self.max_string_length:
            return

        # Skip if matches excluded patterns
        for pattern in self.excluded_patterns:
            if pattern.match(value):
                return

        # Skip if in allowed context
        if self._is_allowed_string_context(node, value):
            return

        # Determine severity
        severity = self._determine_string_severity(value)

        violation = Violation(
            detector_type=self.detector_type,
            severity=severity,
            message=f"Magic string detected: '{value[:50]}{'...' if len(value) > 50 else ''}'",
            location=self.get_node_location(node, file_path),
            details={
                "value": value,
                "length": len(value),
                "context": self._get_string_context(node),
            },
            suggestion=(
                f"Extract this string into a named constant, "
                f"e.g., DEFAULT_ENCODING = '{value}' or ERROR_MESSAGE = '{value[:30]}...'"
            ),
        )
        result.add_violation(violation)

    def _is_allowed_numeric_context(self, node: ast.AST) -> bool:
        """Check if numeric literal is in an allowed context.
        
        Args:
            node: AST node.
            
        Returns:
            True if context is allowed.
        """
        parent = getattr(node, "parent", None)
        if parent is None:
            return False

        # Allow in subscripts (indexing)
        if isinstance(parent, ast.Subscript):
            return True

        # Allow in slice operations
        if isinstance(parent, ast.Slice):
            return True

        # Allow in comparisons with 0
        if isinstance(parent, ast.Compare):
            return True

        return False

    def _is_allowed_string_context(self, node: ast.AST, value: str) -> bool:
        """Check if string literal is in an allowed context.
        
        Args:
            node: AST node.
            value: String value.
            
        Returns:
            True if context is allowed.
        """
        parent = getattr(node, "parent", None)
        if parent is None:
            return False

        # Allow format strings
        if isinstance(parent, ast.JoinedStr):
            return True

        # Allow in logging calls (first argument is often a format string)
        if isinstance(parent, ast.Call):
            func = parent.func
            if isinstance(func, ast.Attribute):
                if func.attr in ["debug", "info", "warning", "error", "critical"]:
                    # Check if this is the first argument (format string)
                    if parent.args and parent.args[0] is node:
                        return True

        # Allow URLs and paths that look like URLs
        if value.startswith(("http://", "https://", "ftp://", "file://")):
            return True

        return False

    def _determine_numeric_severity(self, value: int | float) -> Severity:
        """Determine severity for a numeric literal.
        
        Args:
            value: Numeric value.
            
        Returns:
            Severity level.
        """
        # Large numbers are more likely to be meaningful
        if isinstance(value, int):
            if abs(value) > 10000:
                return Severity.HIGH
            elif abs(value) > 1000:
                return Severity.MEDIUM
            elif abs(value) > 100:
                return Severity.LOW

        # Floats with many decimals
        if isinstance(value, float):
            str_val = str(value)
            if "." in str_val:
                decimals = len(str_val.split(".")[1])
                if decimals > 3:
                    return Severity.MEDIUM

        return Severity.LOW

    def _determine_string_severity(self, value: str) -> Severity:
        """Determine severity for a string literal.
        
        Args:
            value: String value.
            
        Returns:
            Severity level.
        """
        # SQL queries are high severity
        if any(keyword in value.upper() for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE"]):
            return Severity.CRITICAL

        # Error messages
        if any(keyword in value.lower() for keyword in ["error", "exception", "failed"]):
            return Severity.HIGH

        # Configuration values
        if any(keyword in value.lower() for keyword in ["config", "setting", "timeout", "limit"]):
            return Severity.MEDIUM

        return Severity.LOW

    def _get_numeric_context(self, node: ast.AST) -> str:
        """Get context description for numeric literal.
        
        Args:
            node: AST node.
            
        Returns:
            Context description.
        """
        parent = getattr(node, "parent", None)
        if parent is None:
            return "unknown"

        return type(parent).__name__

    def _get_string_context(self, node: ast.AST) -> str:
        """Get context description for string literal.
        
        Args:
            node: AST node.
            
        Returns:
            Context description.
        """
        parent = getattr(node, "parent", None)
        if parent is None:
            return "unknown"

        return type(parent).__name__
