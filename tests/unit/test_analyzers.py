"""Unit tests for ArchGuard analyzers."""

from __future__ import annotations

from pathlib import Path

from archguard.analyzers.base import ASTAnalyzer, FileCollector
from archguard.analyzers.dependency_graph import DependencyGraphBuilder


class TestFileCollector:
    """Tests for FileCollector."""

    def test_collects_python_files(self, tmp_path: Path) -> None:
        """Test that Python files are collected."""
        # Create test files
        (tmp_path / "file1.py").write_text("# test")
        (tmp_path / "file2.py").write_text("# test")
        (tmp_path / "not_python.txt").write_text("text")

        collector = FileCollector()
        files = list(collector.collect(tmp_path))

        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        """Test that __pycache__ is excluded."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.cpython-310.pyc").write_text("")
        (tmp_path / "real.py").write_text("# test")

        collector = FileCollector()
        files = list(collector.collect(tmp_path))

        assert len(files) == 1
        assert files[0].name == "real.py"

    def test_excludes_test_files_by_default(self, tmp_path: Path) -> None:
        """Test that test files are excluded by default."""
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "test_main.py").write_text("# test")

        collector = FileCollector(include_tests=False)
        files = list(collector.collect(tmp_path))

        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_includes_test_files_when_enabled(self, tmp_path: Path) -> None:
        """Test that test files can be included."""
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "test_main.py").write_text("# test")

        collector = FileCollector(include_tests=True)
        files = list(collector.collect(tmp_path))

        assert len(files) == 2

    def test_count_files(self, tmp_path: Path) -> None:
        """Test file counting."""
        (tmp_path / "file1.py").write_text("# test")
        (tmp_path / "file2.py").write_text("# test")

        collector = FileCollector()
        count = collector.count_files(tmp_path)

        assert count == 2


class TestASTAnalyzer:
    """Tests for ASTAnalyzer base class."""

    def test_can_analyze_python_files(self, tmp_path: Path) -> None:
        """Test that Python files can be analyzed."""
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1")

        class TestAnalyzer(ASTAnalyzer):
            def _analyze_ast(self, tree, file_path, result):
                pass

        analyzer = TestAnalyzer()
        assert analyzer.can_analyze(file_path) is True

    def test_cannot_analyze_non_python_files(self, tmp_path: Path) -> None:
        """Test that non-Python files cannot be analyzed."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("text")

        class TestAnalyzer(ASTAnalyzer):
            def _analyze_ast(self, tree, file_path, result):
                pass

        analyzer = TestAnalyzer()
        assert analyzer.can_analyze(file_path) is False

    def test_parses_valid_python(self, tmp_path: Path) -> None:
        """Test parsing of valid Python code."""
        file_path = tmp_path / "test.py"
        file_path.write_text("""
def hello():
    return "world"

class MyClass:
    pass
""")

        class TestAnalyzer(ASTAnalyzer):
            def _analyze_ast(self, tree, file_path, result):
                # Count function definitions
                import ast
                func_count = len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)])
                result.metrics["function_count"] = func_count

        analyzer = TestAnalyzer()
        result = analyzer.analyze(file_path)

        assert result.metrics.get("function_count") == 1

    def test_handles_syntax_error(self, tmp_path: Path) -> None:
        """Test handling of syntax errors."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def broken(:")  # Invalid syntax

        class TestAnalyzer(ASTAnalyzer):
            def _analyze_ast(self, tree, file_path, result):
                pass

        analyzer = TestAnalyzer()
        result = analyzer.analyze(file_path)

        assert len(result.errors) > 0


class TestDependencyGraphBuilder:
    """Tests for DependencyGraphBuilder."""

    def test_builds_graph_from_files(self, tmp_path: Path) -> None:
        """Test building dependency graph."""
        # Create a simple module structure
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "module_a.py").write_text("""
from .module_b import func_b

def func_a():
    return func_b()
""")
        (pkg / "module_b.py").write_text("""
def func_b():
    return "hello"
""")

        builder = DependencyGraphBuilder(tmp_path)
        graph = builder.build_graph()

        # Should have nodes for both modules
        assert len(list(graph.nodes)) >= 2

    def test_finds_no_cycles_in_simple_project(self, tmp_path: Path) -> None:
        """Test that simple projects have no cycles."""
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "module_a.py").write_text("x = 1")
        (pkg / "module_b.py").write_text("y = 2")

        builder = DependencyGraphBuilder(tmp_path)
        builder.build_graph()
        cycles = builder.find_cycles()

        assert len(cycles) == 0

    def test_extracts_imports(self, tmp_path: Path) -> None:
        """Test import extraction."""
        file_path = tmp_path / "test.py"
        file_path.write_text("""
import os
import sys
from collections import defaultdict
from typing import List
""")

        builder = DependencyGraphBuilder(tmp_path)
        imports = builder.get_imports(file_path)

        assert len(imports) == 4
        import_modules = [imp.module for imp in imports]
        assert "os" in import_modules
        assert "sys" in import_modules
        assert "collections" in import_modules
        assert "typing" in import_modules

    def test_path_to_module_conversion(self, tmp_path: Path) -> None:
        """Test converting file path to module name."""
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "module.py").write_text("x = 1")

        builder = DependencyGraphBuilder(tmp_path)
        module_name = builder._path_to_module(pkg / "module.py")

        assert module_name == "mypackage.module"

    def test_handles_init_files(self, tmp_path: Path) -> None:
        """Test handling of __init__.py files."""
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        init_file = pkg / "__init__.py"
        init_file.write_text("x = 1")

        builder = DependencyGraphBuilder(tmp_path)
        module_name = builder._path_to_module(init_file)

        assert module_name == "mypackage"
