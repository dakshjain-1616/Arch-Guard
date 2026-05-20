"""Dependency graph builder for analyzing module relationships."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from archguard.types import PathLike

logger = logging.getLogger(__name__)


@dataclass
class ImportInfo:
    """Information about an import statement."""

    module: str
    names: list[str] = field(default_factory=list)
    is_from_import: bool = False
    level: int = 0  # Relative import level (0 = absolute)
    line: int = 0

    @property
    def is_relative(self) -> bool:
        """Check if this is a relative import."""
        return self.level > 0

    @property
    def is_external(self) -> bool:
        """Check if this is an external (non-project) import."""
        # Simple heuristic: external packages don't start with .
        if self.is_relative:
            return False
        # Common external packages
        external_prefixes = (
            "os", "sys", "json", "re", "collections", "typing", "pathlib",
            "abc", "dataclasses", "enum", "logging", "functools", "itertools",
            "pytest", "unittest", "mock",
        )
        return self.module.startswith(external_prefixes) or "." not in self.module


class DependencyGraphBuilder:
    """Builds a dependency graph from Python source files."""

    def __init__(self, project_root: PathLike) -> None:
        """Initialize the dependency graph builder.
        
        Args:
            project_root: Root directory of the project.
        """
        self.project_root = Path(project_root).resolve()
        self.graph: nx.DiGraph = nx.DiGraph()
        self._module_cache: dict[str, Path] = {}
        self._imports_cache: dict[Path, list[ImportInfo]] = {}

    def build_graph(self, files: list[Path] | None = None) -> nx.DiGraph:
        """Build the dependency graph.
        
        Args:
            files: Optional list of files to analyze. If None, scans project.
            
        Returns:
            NetworkX directed graph of dependencies.
        """
        self.graph = nx.DiGraph()

        if files is None:
            files = list(self._collect_python_files())

        # First pass: index all modules
        for file_path in files:
            module_name = self._path_to_module(file_path)
            if module_name:
                self._module_cache[module_name] = file_path
                self.graph.add_node(module_name, file_path=str(file_path))

        # Second pass: build edges
        for file_path in files:
            self._analyze_file_imports(file_path)

        return self.graph

    def _collect_python_files(self) -> list[Path]:
        """Collect all Python files in the project.
        
        Returns:
            List of Python file paths.
        """
        files = []
        exclude = {"__pycache__", ".git", ".venv", "venv", "node_modules"}

        for path in self.project_root.rglob("*.py"):
            if any(ex in str(path) for ex in exclude):
                continue
            files.append(path)

        return files

    def _path_to_module(self, file_path: Path) -> str | None:
        """Convert a file path to a module name.
        
        Args:
            file_path: Path to the Python file.
            
        Returns:
            Module name or None if not in project.
        """
        try:
            rel_path = file_path.relative_to(self.project_root)
            parts = list(rel_path.parts)

            # Remove .py extension
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]

            # Handle __init__.py
            if parts[-1] == "__init__":
                parts = parts[:-1]

            return ".".join(parts) if parts else None

        except ValueError:
            return None

    def _module_to_path(self, module_name: str) -> Path | None:
        """Convert a module name to a file path.
        
        Args:
            module_name: Module name.
            
        Returns:
            Path to the module file or None.
        """
        if module_name in self._module_cache:
            return self._module_cache[module_name]

        # Try to construct path
        parts = module_name.split(".")
        path = self.project_root / "/".join(parts)

        # Try as file
        py_file = path.with_suffix(".py")
        if py_file.exists():
            return py_file

        # Try as package
        init_file = path / "__init__.py"
        if init_file.exists():
            return init_file

        return None

    def _analyze_file_imports(self, file_path: Path) -> None:
        """Analyze imports in a file and add edges to graph.
        
        Args:
            file_path: Path to analyze.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            source_module = self._path_to_module(file_path)
            if not source_module:
                return

            imports = self._extract_imports(tree)
            self._imports_cache[file_path] = imports

            for import_info in imports:
                target_module = self._resolve_import(import_info, file_path)

                if target_module and target_module != source_module:
                    # Only add edge if target is in our project
                    if target_module in self._module_cache:
                        self.graph.add_edge(
                            source_module,
                            target_module,
                            import_info=import_info,
                        )

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

    def _extract_imports(self, tree: ast.AST) -> list[ImportInfo]:
        """Extract import statements from AST.
        
        Args:
            tree: AST tree.
            
        Returns:
            List of ImportInfo objects.
        """
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        is_from_import=False,
                        level=0,
                        line=node.lineno or 0,
                    ))

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]

                imports.append(ImportInfo(
                    module=module,
                    names=names,
                    is_from_import=True,
                    level=node.level or 0,
                    line=node.lineno or 0,
                ))

        return imports

    def _resolve_import(self, import_info: ImportInfo, source_file: Path) -> str | None:
        """Resolve an import to a module name.
        
        Args:
            import_info: Import information.
            source_file: Source file path.
            
        Returns:
            Resolved module name or None.
        """
        if import_info.is_relative:
            # Resolve relative import
            source_module = self._path_to_module(source_file)
            if not source_module:
                return None

            source_parts = source_module.split(".")
            # Go up levels
            base_parts = source_parts[:-import_info.level] if import_info.level < len(source_parts) else []

            if import_info.module:
                target_parts = base_parts + import_info.module.split(".")
            else:
                target_parts = base_parts

            return ".".join(target_parts) if target_parts else None

        else:
            # Absolute import - check if it's in our project
            module = import_info.module

            # Check if module or any parent is in our cache
            parts = module.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if candidate in self._module_cache:
                    return candidate

            return None

    def find_cycles(self) -> list[list[str]]:
        """Find circular dependencies in the graph.
        
        Returns:
            List of cycles (each cycle is a list of module names).
        """
        try:
            return list(nx.simple_cycles(self.graph))
        except Exception as e:
            logger.error(f"Error finding cycles: {e}")
            return []

    def get_dependencies(self, module: str) -> set[str]:
        """Get all dependencies of a module.
        
        Args:
            module: Module name.
            
        Returns:
            Set of module names that this module depends on.
        """
        if module not in self.graph:
            return set()
        return set(self.graph.successors(module))

    def get_dependents(self, module: str) -> set[str]:
        """Get all modules that depend on a module.
        
        Args:
            module: Module name.
            
        Returns:
            Set of module names that depend on this module.
        """
        if module not in self.graph:
            return set()
        return set(self.graph.predecessors(module))

    def get_imports(self, file_path: Path) -> list[ImportInfo]:
        """Get imports for a file (cached).
        
        Args:
            file_path: Path to the file.
            
        Returns:
            List of ImportInfo objects.
        """
        if file_path not in self._imports_cache:
            self._analyze_file_imports(file_path)

        return self._imports_cache.get(file_path, [])

    def to_dict(self) -> dict:
        """Convert graph to dictionary representation.
        
        Returns:
            Dictionary with nodes and edges.
        """
        return {
            "nodes": [
                {"module": node, **data}
                for node, data in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in self.graph.edges(data=True)
            ],
        }
