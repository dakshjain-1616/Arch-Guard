"""Base analyzer for static code analysis."""

from __future__ import annotations

import ast
import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from pathlib import Path
from typing import Any

from archguard.types import AnalysisResult, Location, PathLike

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Base class for all code analyzers."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize analyzer with configuration.
        
        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def analyze(self, file_path: PathLike, content: str | None = None) -> AnalysisResult:
        """Analyze a file for architecture violations.
        
        Args:
            file_path: Path to the file to analyze.
            content: Optional file content (if already loaded).
            
        Returns:
            AnalysisResult containing violations and metrics.
        """
        pass

    def can_analyze(self, file_path: PathLike) -> bool:
        """Check if this analyzer can handle the given file.
        
        Args:
            file_path: Path to check.
            
        Returns:
            True if the file can be analyzed.
        """
        path = Path(file_path)
        return path.suffix == ".py" and path.exists()


class ASTAnalyzer(BaseAnalyzer):
    """Analyzer that uses Python AST for code analysis."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize AST analyzer.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self._ast_cache: dict[Path, ast.AST] = {}

    def parse_file(self, file_path: PathLike, content: str | None = None) -> ast.AST | None:
        """Parse a Python file into an AST.
        
        Args:
            file_path: Path to the file.
            content: Optional file content.
            
        Returns:
            AST tree or None if parsing fails.
        """
        path = Path(file_path)

        # Check cache
        if path in self._ast_cache:
            return self._ast_cache[path]

        try:
            if content is None:
                content = path.read_text(encoding="utf-8")

            tree = ast.parse(content, filename=str(path))
            self._ast_cache[path] = tree
            return tree

        except SyntaxError as e:
            self.logger.warning(f"Syntax error in {path}: {e}")
            return None
        except UnicodeDecodeError as e:
            self.logger.warning(f"Encoding error in {path}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to parse {path}: {e}")
            return None

    def analyze(self, file_path: PathLike, content: str | None = None) -> AnalysisResult:
        """Analyze file using AST parsing.
        
        Args:
            file_path: Path to analyze.
            content: Optional file content.
            
        Returns:
            AnalysisResult with findings.
        """
        path = Path(file_path)
        result = AnalysisResult(file_path=path)

        if not self.can_analyze(path):
            result.add_error(f"Cannot analyze file: {path}")
            return result

        tree = self.parse_file(path, content)
        if tree is None:
            result.add_error(f"Failed to parse AST for: {path}")
            return result

        # Perform AST-based analysis
        self._analyze_ast(tree, path, result)

        return result

    @abstractmethod
    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze the AST tree.
        
        Args:
            tree: AST tree to analyze.
            file_path: Path to the file.
            result: AnalysisResult to populate.
        """
        pass

    def get_node_location(self, node: ast.AST, file_path: Path) -> Location:
        """Get location info for an AST node.
        
        Args:
            node: AST node.
            file_path: File path.
            
        Returns:
            Location object.
        """
        return Location(
            file_path=file_path,
            line_start=getattr(node, "lineno", 1),
            line_end=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
            column_start=getattr(node, "col_offset", 0),
            column_end=getattr(node, "end_col_offset", 0),
        )


class FileCollector:
    """Collects Python files for analysis."""

    DEFAULT_EXCLUDE_PATTERNS: set[str] = {
        "__pycache__",
        "*.pyc",
        ".git",
        ".venv",
        "venv",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        ".egg-info",
        "build",
        "dist",
    }

    def __init__(
        self,
        exclude_patterns: set[str] | None = None,
        include_tests: bool = False
    ) -> None:
        """Initialize file collector.
        
        Args:
            exclude_patterns: Additional patterns to exclude.
            include_tests: Whether to include test files.
        """
        self.exclude_patterns = self.DEFAULT_EXCLUDE_PATTERNS | (exclude_patterns or set())
        self.include_tests = include_tests

    def collect(self, root_path: PathLike) -> Generator[Path, None, None]:
        """Collect Python files from a directory.
        
        Args:
            root_path: Root directory to search.
            
        Yields:
            Paths to Python files.
        """
        root = Path(root_path)

        if root.is_file():
            if self._should_include(root):
                yield root
            return

        for path in root.rglob("*.py"):
            if self._should_include(path):
                yield path

    def _should_include(self, path: Path) -> bool:
        """Check if a path should be included.
        
        Args:
            path: Path to check.
            
        Returns:
            True if the path should be included.
        """
        path_str = str(path)

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return False

        # Skip test files unless included
        if not self.include_tests:
            if "test_" in path.name or "_test.py" in path.name or "/tests/" in path_str:
                return False

        return True

    def count_files(self, root_path: PathLike) -> int:
        """Count Python files in a directory.
        
        Args:
            root_path: Root directory to search.
            
        Returns:
            Number of Python files.
        """
        return sum(1 for _ in self.collect(root_path))
