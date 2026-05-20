"""Service layer bypass detector."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from archguard.analyzers.base import ASTAnalyzer
from archguard.types import AnalysisResult, DetectorType, Location, Severity, Violation

logger = logging.getLogger(__name__)


class ServiceLayerBypassDetector(ASTAnalyzer):
    """Detects when presentation/controller layers bypass service layer."""

    # Default patterns for different layers
    DEFAULT_CONTROLLER_PATTERNS = [
        r".*controller.*",
        r".*view.*",
        r".*handler.*",
        r".*endpoint.*",
        r".*route.*",
        r".*api.*",
    ]

    DEFAULT_SERVICE_PATTERNS = [
        r".*service.*",
        r".*usecase.*",
        r".*use_case.*",
        r".*application.*",
    ]

    DEFAULT_REPOSITORY_PATTERNS = [
        r".*repository.*",
        r".*dao.*",
        r".*data.*",
        r".*store.*",
        r".*db.*",
        r".*database.*",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize service layer bypass detector.
        
        Args:
            config: Configuration with optional patterns:
                - controller_patterns: Regex patterns for controller layer
                - service_patterns: Regex patterns for service layer
                - repository_patterns: Regex patterns for repository layer
        """
        super().__init__(config)

        self.controller_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.config.get("controller_patterns", self.DEFAULT_CONTROLLER_PATTERNS)
        ]
        self.service_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.config.get("service_patterns", self.DEFAULT_SERVICE_PATTERNS)
        ]
        self.repository_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.config.get("repository_patterns", self.DEFAULT_REPOSITORY_PATTERNS)
        ]

        self.detector_type = DetectorType.SERVICE_LAYER_BYPASS

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze AST for service layer bypasses.
        
        Args:
            tree: AST tree.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        # Check if this is a controller/presentation layer file
        if not self._is_controller_file(file_path):
            return

        # Find all imports
        imports = self._extract_imports(tree)

        # Check for direct repository imports in controller
        for import_info in imports:
            if self._is_repository_import(import_info):
                violation = Violation(
                    detector_type=self.detector_type,
                    severity=Severity.HIGH,
                    message=(
                        f"Controller layer directly imports repository: "
                        f"'{import_info.get('module', 'unknown')}'"
                    ),
                    location=Location(
                        file_path=file_path,
                        line_start=import_info.get("line", 1),
                    ),
                    details={
                        "import_module": import_info["module"],
                        "import_names": import_info.get("names", []),
                        "layer_violation": "controller -> repository (bypasses service)",
                    },
                    suggestion=(
                        "Move repository access through a service layer. "
                        "Controllers should only interact with services, not repositories directly."
                    ),
                )
                result.add_violation(violation)

        # Check for direct repository instantiation/calls in methods
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._analyze_method_for_bypass(node, file_path, result)

    def _is_controller_file(self, file_path: Path) -> bool:
        """Check if file is in controller/presentation layer.
        
        Args:
            file_path: Path to check.
            
        Returns:
            True if controller layer.
        """
        path_str = str(file_path).lower()
        file_name = file_path.stem.lower()

        # Check file name
        for pattern in self.controller_patterns:
            if pattern.match(file_name):
                return True

        # Check path
        for pattern in self.controller_patterns:
            if pattern.search(path_str):
                return True

        return False

    def _is_service_file(self, file_path: Path) -> bool:
        """Check if file is in service layer.
        
        Args:
            file_path: Path to check.
            
        Returns:
            True if service layer.
        """
        path_str = str(file_path).lower()
        file_name = file_path.stem.lower()

        for pattern in self.service_patterns:
            if pattern.match(file_name) or pattern.search(path_str):
                return True

        return False

    def _is_repository_import(self, import_info: dict[str, Any]) -> bool:
        """Check if import is to a repository.
        
        Args:
            import_info: Import information.
            
        Returns:
            True if repository import.
        """
        module = import_info.get("module", "").lower()

        for pattern in self.repository_patterns:
            if pattern.search(module):
                return True

        return False

    def _extract_imports(self, tree: ast.AST) -> list[dict[str, Any]]:
        """Extract imports from AST.
        
        Args:
            tree: AST tree.
            
        Returns:
            List of import information.
        """
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "names": [alias.asname or alias.name],
                        "is_from": False,
                        "line": getattr(node, "lineno", 1),
                    })

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]

                imports.append({
                    "module": module,
                    "names": names,
                    "is_from": True,
                    "line": getattr(node, "lineno", 1),
                })

        return imports

    def _analyze_method_for_bypass(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze a method for layer bypass patterns.
        
        Args:
            node: Function AST node.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        # Look for direct repository instantiation
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    func_name = child.func.id.lower()

                    # Check if calling a repository constructor
                    for pattern in self.repository_patterns:
                        if pattern.search(func_name):
                            violation = Violation(
                                detector_type=self.detector_type,
                                severity=Severity.CRITICAL,
                                message=(
                                    f"Controller directly instantiates repository: "
                                    f"'{child.func.id}'"
                                ),
                                location=self.get_node_location(child, file_path),
                                details={
                                    "function": node.name,
                                    "instantiated_class": child.func.id,
                                    "layer_violation": "controller creates repository",
                                },
                                suggestion=(
                                    "Inject repository through service layer or use dependency injection. "
                                    "Never instantiate repositories directly in controllers."
                                ),
                            )
                            result.add_violation(violation)

                elif isinstance(child.func, ast.Attribute):
                    # Check for method calls on repositories
                    method_name = child.func.attr.lower()

                    # Common repository method patterns
                    repo_methods = ["find", "get", "save", "delete", "update", "query", "insert"]

                    if any(method_name.startswith(m) for m in repo_methods):
                        # Check if receiver might be a repository
                        if isinstance(child.func.value, ast.Name):
                            receiver = child.func.value.id.lower()

                            for pattern in self.repository_patterns:
                                if pattern.search(receiver):
                                    violation = Violation(
                                        detector_type=self.detector_type,
                                        severity=Severity.HIGH,
                                        message=(
                                            f"Controller calls repository method directly: "
                                            f"'{receiver}.{child.func.attr}'"
                                        ),
                                        location=self.get_node_location(child, file_path),
                                        details={
                                            "function": node.name,
                                            "method_call": f"{receiver}.{child.func.attr}",
                                            "layer_violation": "controller -> repository method",
                                        },
                                        suggestion=(
                                            "Move this data access logic to a service layer method"
                                        ),
                                    )
                                    result.add_violation(violation)
                                    break
