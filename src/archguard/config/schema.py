"""Configuration schema and validation for ArchGuard."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DetectorConfig:
    """Configuration for a single detector."""

    enabled: bool = True
    severity: str = "medium"
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetectorConfig:
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            severity=data.get("severity", "medium"),
            options=data.get("options", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "severity": self.severity,
            "options": self.options,
        }


@dataclass
class LayerConfig:
    """Configuration for architecture layers."""

    name: str = ""
    patterns: list[str] = field(default_factory=list)
    allowed_calls: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> LayerConfig:
        """Create from dictionary."""
        return cls(
            name=name,
            patterns=data.get("patterns", []),
            allowed_calls=data.get("allowed_calls", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "patterns": self.patterns,
            "allowed_calls": self.allowed_calls,
        }


@dataclass
class ArchGuardConfig:
    """Main configuration for ArchGuard."""

    # Project settings
    project_name: str = ""
    project_root: Path = field(default_factory=lambda: Path())

    # Analysis settings
    include_patterns: list[str] = field(default_factory=lambda: ["**/*.py"])
    exclude_patterns: list[str] = field(default_factory=list)
    include_tests: bool = False

    # Detector configurations
    detectors: dict[str, DetectorConfig] = field(default_factory=dict)

    # Layer configuration
    layers: dict[str, LayerConfig] = field(default_factory=dict)

    # Output settings
    output_format: str = "table"
    output_file: Path | None = None
    fail_on_violations: bool = False
    severity_threshold: str = "low"

    # Git settings
    git_enabled: bool = True
    compare_branch: str = "main"
    max_commits: int = 10

    # Trend analysis
    trend_enabled: bool = True
    trend_history_limit: int = 10

    def __post_init__(self) -> None:
        """Initialize default detector configs if not set."""
        default_detectors = [
            "circular_dependency",
            "god_class",
            "service_layer_bypass",
            "magic_value",
            "cyclomatic_complexity",
            "layer_violation",
        ]

        for detector in default_detectors:
            if detector not in self.detectors:
                self.detectors[detector] = DetectorConfig()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchGuardConfig:
        """Create configuration from dictionary."""
        # Parse detectors
        detectors = {}
        for name, detector_data in data.get("detectors", {}).items():
            detectors[name] = DetectorConfig.from_dict(detector_data)

        # Parse layers
        layers = {}
        for name, layer_data in data.get("layers", {}).items():
            layers[name] = LayerConfig.from_dict(name, layer_data)

        return cls(
            project_name=data.get("project_name", ""),
            project_root=Path(data.get("project_root", ".")),
            include_patterns=data.get("include_patterns", ["**/*.py"]),
            exclude_patterns=data.get("exclude_patterns", []),
            include_tests=data.get("include_tests", False),
            detectors=detectors,
            layers=layers,
            output_format=data.get("output_format", "table"),
            output_file=Path(data["output_file"]) if data.get("output_file") else None,
            fail_on_violations=data.get("fail_on_violations", False),
            severity_threshold=data.get("severity_threshold", "low"),
            git_enabled=data.get("git_enabled", True),
            compare_branch=data.get("compare_branch", "main"),
            max_commits=data.get("max_commits", 10),
            trend_enabled=data.get("trend_enabled", True),
            trend_history_limit=data.get("trend_history_limit", 10),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_name": self.project_name,
            "project_root": str(self.project_root),
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "include_tests": self.include_tests,
            "detectors": {
                name: config.to_dict()
                for name, config in self.detectors.items()
            },
            "layers": {
                name: config.to_dict()
                for name, config in self.layers.items()
            },
            "output_format": self.output_format,
            "output_file": str(self.output_file) if self.output_file else None,
            "fail_on_violations": self.fail_on_violations,
            "severity_threshold": self.severity_threshold,
            "git_enabled": self.git_enabled,
            "compare_branch": self.compare_branch,
            "max_commits": self.max_commits,
            "trend_enabled": self.trend_enabled,
            "trend_history_limit": self.trend_history_limit,
        }

    def get_detector_config(self, name: str) -> DetectorConfig:
        """Get configuration for a detector."""
        return self.detectors.get(name, DetectorConfig())

    def is_detector_enabled(self, name: str) -> bool:
        """Check if a detector is enabled."""
        config = self.detectors.get(name)
        return config.enabled if config else False


class ConfigValidator:
    """Validates configuration data."""

    VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
    VALID_OUTPUT_FORMATS = {"table", "json", "yaml", "markdown", "html"}
    VALID_DETECTORS = {
        "circular_dependency",
        "god_class",
        "service_layer_bypass",
        "magic_value",
        "cyclomatic_complexity",
        "layer_violation",
    }

    @classmethod
    def validate(cls, data: dict[str, Any]) -> list[str]:
        """Validate configuration data.
        
        Args:
            data: Configuration dictionary.
            
        Returns:
            List of validation errors (empty if valid).
        """
        errors = []

        # Validate severity_threshold
        severity = data.get("severity_threshold", "low")
        if severity not in cls.VALID_SEVERITIES:
            errors.append(
                f"Invalid severity_threshold: {severity}. "
                f"Must be one of: {cls.VALID_SEVERITIES}"
            )

        # Validate output_format
        output_format = data.get("output_format", "table")
        if output_format not in cls.VALID_OUTPUT_FORMATS:
            errors.append(
                f"Invalid output_format: {output_format}. "
                f"Must be one of: {cls.VALID_OUTPUT_FORMATS}"
            )

        # Validate detectors
        detectors = data.get("detectors", {})
        for name in detectors.keys():
            if name not in cls.VALID_DETECTORS:
                errors.append(
                    f"Unknown detector: {name}. "
                    f"Valid detectors: {cls.VALID_DETECTORS}"
                )

        # Validate detector configs
        for name, config in detectors.items():
            if isinstance(config, dict):
                severity = config.get("severity")
                if severity and severity not in cls.VALID_SEVERITIES:
                    errors.append(
                        f"Invalid severity for {name}: {severity}"
                    )

        return errors


class ConfigLoader:
    """Loads configuration from files."""

    DEFAULT_CONFIG_NAMES = [
        ".archguard.yml",
        ".archguard.yaml",
        "archguard.yml",
        "archguard.yaml",
        ".archguardrc",
        "pyproject.toml",
    ]

    @classmethod
    def find_config(cls, start_path: Path | None = None) -> Path | None:
        """Find configuration file starting from given path.
        
        Args:
            start_path: Starting path (default: current directory).
            
        Returns:
            Path to config file or None.
        """
        if start_path is None:
            start_path = Path.cwd()

        path = start_path.resolve()

        while path.parent != path:
            for config_name in cls.DEFAULT_CONFIG_NAMES:
                config_path = path / config_name
                if config_path.exists():
                    return config_path
            path = path.parent

        return None

    @classmethod
    def load(cls, config_path: Path | None = None) -> ArchGuardConfig:
        """Load configuration from file.
        
        Args:
            config_path: Path to config file. If None, searches for config.
            
        Returns:
            Loaded configuration.
        """
        if config_path is None:
            config_path = cls.find_config()

        if config_path is None or not config_path.exists():
            # Return default config
            return ArchGuardConfig()

        # Load based on file type
        if config_path.suffix == ".toml":
            return cls._load_from_toml(config_path)
        else:
            return cls._load_from_yaml(config_path)

    @classmethod
    def _load_from_yaml(cls, path: Path) -> ArchGuardConfig:
        """Load from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Validate
        errors = ConfigValidator.validate(data)
        if errors:
            raise ValueError(f"Config validation errors: {'; '.join(errors)}")

        return ArchGuardConfig.from_dict(data)

    @classmethod
    def _load_from_toml(cls, path: Path) -> ArchGuardConfig:
        """Load from TOML file (pyproject.toml)."""
        try:
            import tomllib
        except ImportError:
            import importlib
            tomllib = importlib.import_module("tomli")

        with open(path, "rb") as f:
            data = tomllib.load(f)

        # Extract archguard section
        archguard_data = data.get("tool", {}).get("archguard", {})

        # Validate
        errors = ConfigValidator.validate(archguard_data)
        if errors:
            raise ValueError(f"Config validation errors: {'; '.join(errors)}")

        return ArchGuardConfig.from_dict(archguard_data)

    @classmethod
    def save(cls, config: ArchGuardConfig, path: Path) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration to save.
            path: Path to save to.
        """
        data = config.to_dict()

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def create_default_config() -> str:
    """Create default configuration as YAML string."""
    return """# ArchGuard Configuration
# See documentation for all options

project_name: "My Project"
project_root: "."

# File patterns to include/exclude
include_patterns:
  - "**/*.py"

exclude_patterns:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/__pycache__/**"
  - "**/venv/**"
  - "**/.venv/**"
  - "**/node_modules/**"

include_tests: false

# Detector configurations
detectors:
  circular_dependency:
    enabled: true
    severity: high
    options:
      min_cycle_length: 2
      max_cycles: 100

  god_class:
    enabled: true
    severity: medium
    options:
      max_methods: 20
      max_attributes: 15
      max_lines: 500

  service_layer_bypass:
    enabled: true
    severity: high
    options:
      controller_patterns:
        - ".*controller.*"
        - ".*view.*"
        - ".*handler.*"
      service_patterns:
        - ".*service.*"
        - ".*usecase.*"
      repository_patterns:
        - ".*repository.*"
        - ".*dao.*"

  magic_value:
    enabled: true
    severity: low
    options:
      min_string_length: 3
      max_string_length: 100

  cyclomatic_complexity:
    enabled: true
    severity: medium
    options:
      thresholds:
        low: 10
        medium: 20
        high: 30
        critical: 50

  layer_violation:
    enabled: true
    severity: high
    options:
      layers:
        presentation:
          patterns:
            - ".*controller.*"
            - ".*view.*"
            - ".*handler.*"
          allowed_calls:
            - service
        service:
          patterns:
            - ".*service.*"
            - ".*usecase.*"
          allowed_calls:
            - domain
            - repository
        domain:
          patterns:
            - ".*domain.*"
            - ".*model.*"
          allowed_calls: []
        repository:
          patterns:
            - ".*repository.*"
            - ".*dao.*"
          allowed_calls:
            - infrastructure

# Output settings
output_format: table
fail_on_violations: false
severity_threshold: low

# Git integration
git_enabled: true
compare_branch: main
max_commits: 10

# Trend analysis
trend_enabled: true
trend_history_limit: 10
"""
