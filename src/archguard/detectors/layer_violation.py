"""Layer violation detector - finds violations of layered architecture."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from archguard.analyzers.base import ASTAnalyzer
from archguard.types import AnalysisResult, DetectorType, Location, Severity, Violation

logger = logging.getLogger(__name__)


class LayerViolationDetector(ASTAnalyzer):
    """Detects violations of layered architecture patterns."""

    # Default layer definitions
    DEFAULT_LAYERS = {
        "presentation": {
            "patterns": [
                r".*controller.*",
                r".*view.*",
                r".*handler.*",
                r".*endpoint.*",
                r".*route.*",
                r".*api.*",
                r".*cli.*",
                r".*web.*",
            ],
            "allowed_calls": ["service", "application"],
        },
        "service": {
            "patterns": [
                r".*service.*",
                r".*usecase.*",
                r".*use_case.*",
                r".*application.*",
                r".*business.*",
            ],
            "allowed_calls": ["repository", "domain", "infrastructure"],
        },
        "domain": {
            "patterns": [
                r".*domain.*",
                r".*model.*",
                r".*entity.*",
                r".*value.*",
                r".*aggregate.*",
            ],
            "allowed_calls": [],  # Domain should be pure
        },
        "repository": {
            "patterns": [
                r".*repository.*",
                r".*dao.*",
                r".*data.*",
                r".*store.*",
            ],
            "allowed_calls": ["infrastructure", "database"],
        },
        "infrastructure": {
            "patterns": [
                r".*infrastructure.*",
                r".*external.*",
                r".*adapter.*",
                r".*client.*",
                r".*db.*",
                r".*database.*",
            ],
            "allowed_calls": [],  # Infrastructure is at the bottom
        },
    }

    # Layer dependency rules (who can call whom)
    DEFAULT_RULES = {
        "presentation": ["service"],
        "service": ["domain", "repository", "infrastructure"],
        "domain": [],
        "repository": ["infrastructure"],
        "infrastructure": [],
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize layer violation detector.
        
        Args:
            config: Configuration with optional settings:
                - layers: Layer definitions with patterns
                - rules: Layer dependency rules
        """
        super().__init__(config)

        self.layers = self.DEFAULT_LAYERS.copy()
        self.layers.update(self.config.get("layers", {}))

        self.rules = self.DEFAULT_RULES.copy()
        self.rules.update(self.config.get("rules", {}))

        # Compile patterns
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        for layer_name, layer_config in self.layers.items():
            patterns = layer_config.get("patterns", [])
            self._compiled_patterns[layer_name] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        self.detector_type = DetectorType.LAYER_VIOLATION

    def _analyze_ast(
        self,
        tree: ast.AST,
        file_path: Path,
        result: AnalysisResult
    ) -> None:
        """Analyze AST for layer violations.
        
        Args:
            tree: AST tree.
            file_path: File path.
            result: AnalysisResult to populate.
        """
        # Determine which layer this file belongs to
        source_layer = self._identify_layer(file_path)
        if not source_layer:
            return  # File doesn't belong to any defined layer

        # Get allowed target layers
        allowed_targets = self.rules.get(source_layer, [])

        # Extract imports
        imports = self._extract_imports(tree)

        for import_info in imports:
            target_layer = self._identify_layer_from_module(import_info["module"])

            if target_layer and target_layer not in allowed_targets:
                # Check if this is a direct violation
                if target_layer != source_layer:  # Same layer is OK
                    violation = self._create_violation(
                        source_layer,
                        target_layer,
                        import_info,
                        file_path,
                        allowed_targets,
                    )
                    result.add_violation(violation)

        # Also check for direct instantiation
        self._check_instantiation(tree, file_path, source_layer, allowed_targets, result)

    def _identify_layer(self, file_path: Path) -> str | None:
        """Identify which layer a file belongs to.
        
        Args:
            file_path: File path.
            
        Returns:
            Layer name or None.
        """
        path_str = str(file_path).lower()
        file_name = file_path.stem.lower()

        for layer_name, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(file_name) or pattern.search(path_str):
                    return layer_name

        return None

    def _identify_layer_from_module(self, module_name: str) -> str | None:
        """Identify layer from module name.
        
        Args:
            module_name: Module name.
            
        Returns:
            Layer name or None.
        """
        module_lower = module_name.lower()

        for layer_name, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(module_lower):
                    return layer_name

        return None

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

    def _check_instantiation(
        self,
        tree: ast.AST,
        file_path: Path,
        source_layer: str,
        allowed_targets: list[str],
        result: AnalysisResult,
    ) -> None:
        """Check for direct instantiation of lower layer classes.
        
        Args:
            tree: AST tree.
            file_path: File path.
            source_layer: Source layer name.
            allowed_targets: Allowed target layers.
            result: AnalysisResult to populate.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    # Direct class instantiation
                    class_name = node.func.id

                    # Try to infer layer from class name
                    target_layer = self._infer_layer_from_class_name(class_name)

                    if target_layer and target_layer not in allowed_targets:
                        if target_layer != source_layer:
                            violation = Violation(
                                detector_type=self.detector_type,
                                severity=Severity.CRITICAL,
                                message=(
                                    f"Layer violation: {source_layer} layer directly "
                                    f"instantiates {target_layer} class '{class_name}'"
                                ),
                                location=self.get_node_location(node, file_path),
                                details={
                                    "source_layer": source_layer,
                                    "target_layer": target_layer,
                                    "instantiated_class": class_name,
                                    "violation_type": "direct_instantiation",
                                    "allowed_targets": allowed_targets,
                                },
                                suggestion=(
                                    f"Use dependency injection or a factory pattern "
                                    f"to avoid direct instantiation of {target_layer} "
                                    f"classes from {source_layer} layer"
                                ),
                            )
                            result.add_violation(violation)

    def _infer_layer_from_class_name(self, class_name: str) -> str | None:
        """Try to infer layer from class name conventions.
        
        Args:
            class_name: Class name.
            
        Returns:
            Inferred layer or None.
        """
        name_lower = class_name.lower()

        # Common naming conventions
        conventions = {
            "presentation": ["controller", "handler", "view", "endpoint", "route"],
            "service": ["service", "usecase", "usecase", "application"],
            "domain": ["entity", "aggregate", "valueobject", "domain"],
            "repository": ["repository", "dao", "dataaccess"],
            "infrastructure": ["client", "adapter", "gateway", "provider"],
        }

        for layer, keywords in conventions.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return layer

        return None

    def _create_violation(
        self,
        source_layer: str,
        target_layer: str,
        import_info: dict[str, Any],
        file_path: Path,
        allowed_targets: list[str],
    ) -> Violation:
        """Create a layer violation.
        
        Args:
            source_layer: Source layer.
            target_layer: Target layer.
            import_info: Import information.
            file_path: File path.
            allowed_targets: Allowed target layers.
            
        Returns:
            Violation object.
        """
        # Determine severity based on layer distance
        severity = self._determine_severity(source_layer, target_layer)

        return Violation(
            detector_type=self.detector_type,
            severity=severity,
            message=(
                f"Layer violation: {source_layer} layer imports from "
                f"{target_layer} layer ('{import_info['module']}')"
            ),
            location=Location(
                file_path=file_path,
                line_start=import_info.get("line", 1),
            ),
            details={
                "source_layer": source_layer,
                "target_layer": target_layer,
                "import_module": import_info["module"],
                "import_names": import_info.get("names", []),
                "violation_type": "import",
                "allowed_targets": allowed_targets,
            },
            suggestion=(
                f"{source_layer} layer should only interact with: "
                f"{', '.join(allowed_targets) if allowed_targets else 'no other layers'}. "
                f"Consider moving this dependency to an allowed layer or "
                f"refactoring the architecture."
            ),
        )

    def _determine_severity(self, source_layer: str, target_layer: str) -> Severity:
        """Determine severity based on layer violation type.
        
        Args:
            source_layer: Source layer.
            target_layer: Target layer.
            
        Returns:
            Severity level.
        """
        # Define layer order (higher index = lower layer)
        layer_order = ["presentation", "service", "domain", "repository", "infrastructure"]

        try:
            source_idx = layer_order.index(source_layer)
            target_idx = layer_order.index(target_layer)
        except ValueError:
            return Severity.MEDIUM

        # Calling down multiple layers is worse
        layer_distance = target_idx - source_idx

        if layer_distance >= 3:
            return Severity.CRITICAL
        elif layer_distance == 2:
            return Severity.HIGH
        elif layer_distance == 1:
            return Severity.MEDIUM
        else:
            # Same layer or calling up (also bad)
            return Severity.HIGH
