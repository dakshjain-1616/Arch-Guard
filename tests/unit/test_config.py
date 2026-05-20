"""Unit tests for ArchGuard configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from archguard.config.schema import (
    ArchGuardConfig,
    ConfigLoader,
    ConfigValidator,
    DetectorConfig,
    create_default_config,
)


class TestDetectorConfig:
    """Tests for DetectorConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DetectorConfig()

        assert config.enabled is True
        assert config.severity == "medium"
        assert config.options == {}

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "enabled": False,
            "severity": "high",
            "options": {"max_methods": 10},
        }
        config = DetectorConfig.from_dict(data)

        assert config.enabled is False
        assert config.severity == "high"
        assert config.options == {"max_methods": 10}

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        config = DetectorConfig(
            enabled=False,
            severity="critical",
            options={"threshold": 5},
        )
        data = config.to_dict()

        assert data["enabled"] is False
        assert data["severity"] == "critical"
        assert data["options"] == {"threshold": 5}


class TestArchGuardConfig:
    """Tests for ArchGuardConfig."""

    def test_default_configuration(self) -> None:
        """Test default configuration."""
        config = ArchGuardConfig()

        assert config.project_name == ""
        assert config.output_format == "table"
        assert config.fail_on_violations is False
        assert config.severity_threshold == "low"
        assert config.git_enabled is True
        assert config.compare_branch == "main"

    def test_default_detectors_initialized(self) -> None:
        """Test that default detectors are initialized."""
        config = ArchGuardConfig()

        expected_detectors = [
            "circular_dependency",
            "god_class",
            "service_layer_bypass",
            "magic_value",
            "cyclomatic_complexity",
            "layer_violation",
        ]

        for detector in expected_detectors:
            assert detector in config.detectors
            assert config.detectors[detector].enabled is True

    def test_from_dict(self) -> None:
        """Test creating from dictionary."""
        data = {
            "project_name": "My Project",
            "output_format": "json",
            "detectors": {
                "god_class": {
                    "enabled": False,
                    "severity": "high",
                }
            },
        }
        config = ArchGuardConfig.from_dict(data)

        assert config.project_name == "My Project"
        assert config.output_format == "json"
        assert config.detectors["god_class"].enabled is False
        assert config.detectors["god_class"].severity == "high"
        # Other detectors should still be enabled
        assert config.detectors["magic_value"].enabled is True

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        config = ArchGuardConfig(
            project_name="Test",
            output_format="yaml",
        )
        data = config.to_dict()

        assert data["project_name"] == "Test"
        assert data["output_format"] == "yaml"
        assert "detectors" in data

    def test_get_detector_config(self) -> None:
        """Test getting detector configuration."""
        config = ArchGuardConfig()

        god_class_config = config.get_detector_config("god_class")
        assert god_class_config.enabled is True

        # Unknown detector returns default
        unknown_config = config.get_detector_config("unknown")
        assert unknown_config.enabled is True

    def test_is_detector_enabled(self) -> None:
        """Test checking if detector is enabled."""
        config = ArchGuardConfig()
        config.detectors["god_class"].enabled = False

        assert config.is_detector_enabled("god_class") is False
        assert config.is_detector_enabled("magic_value") is True
        assert config.is_detector_enabled("unknown") is False


class TestConfigValidator:
    """Tests for ConfigValidator."""

    def test_valid_configuration(self) -> None:
        """Test validation of valid configuration."""
        data = {
            "output_format": "json",
            "severity_threshold": "medium",
            "detectors": {
                "god_class": {"enabled": True, "severity": "high"},
            },
        }
        errors = ConfigValidator.validate(data)

        assert len(errors) == 0

    def test_invalid_output_format(self) -> None:
        """Test validation of invalid output format."""
        data = {"output_format": "xml"}
        errors = ConfigValidator.validate(data)

        assert len(errors) == 1
        assert "output_format" in errors[0]

    def test_invalid_severity(self) -> None:
        """Test validation of invalid severity."""
        data = {"severity_threshold": "extreme"}
        errors = ConfigValidator.validate(data)

        assert len(errors) == 1
        assert "severity_threshold" in errors[0]

    def test_unknown_detector(self) -> None:
        """Test validation of unknown detector."""
        data = {"detectors": {"unknown_detector": {"enabled": True}}}
        errors = ConfigValidator.validate(data)

        assert len(errors) == 1
        assert "unknown_detector" in errors[0]

    def test_invalid_detector_severity(self) -> None:
        """Test validation of invalid detector severity."""
        data = {
            "detectors": {
                "god_class": {"severity": "extreme"},
            },
        }
        errors = ConfigValidator.validate(data)

        assert len(errors) == 1
        assert "god_class" in errors[0]


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_default_config(self) -> None:
        """Test loading default configuration."""
        config = ConfigLoader.load()

        assert isinstance(config, ArchGuardConfig)
        assert config.output_format == "table"

    def test_load_from_yaml_file(self, tmp_path: Path) -> None:
        """Test loading from YAML file."""
        config_file = tmp_path / ".archguard.yml"
        config_file.write_text("""
project_name: Test Project
output_format: json
detectors:
  god_class:
    enabled: false
    severity: high
""")

        config = ConfigLoader.load(config_file)

        assert config.project_name == "Test Project"
        assert config.output_format == "json"
        assert config.detectors["god_class"].enabled is False

    def test_find_config_in_parent_directory(self, tmp_path: Path) -> None:
        """Test finding config in parent directory."""
        # Create config in parent
        config_file = tmp_path / ".archguard.yml"
        config_file.write_text("project_name: Parent Project")

        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Change to subdirectory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            found = ConfigLoader.find_config()
            assert found == config_file
        finally:
            os.chdir(original_cwd)

    def test_save_config(self, tmp_path: Path) -> None:
        """Test saving configuration."""
        config = ArchGuardConfig(
            project_name="Saved Project",
            output_format="yaml",
        )

        config_file = tmp_path / "saved_config.yml"
        ConfigLoader.save(config, config_file)

        assert config_file.exists()

        # Load and verify
        loaded = ConfigLoader.load(config_file)
        assert loaded.project_name == "Saved Project"
        assert loaded.output_format == "yaml"


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_returns_yaml_string(self) -> None:
        """Test that function returns YAML string."""
        config = create_default_config()

        assert isinstance(config, str)
        assert "project_name" in config
        assert "detectors:" in config

    def test_valid_yaml(self) -> None:
        """Test that returned string is valid YAML."""
        config = create_default_config()

        # Should parse without error
        data = yaml.safe_load(config)

        assert isinstance(data, dict)
        assert "project_name" in data
        assert "detectors" in data
