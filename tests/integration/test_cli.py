"""Integration tests for ArchGuard CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


class TestCLIIntegration:
    """Integration tests for the CLI."""

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample project for testing."""
        # Create a simple Python project structure
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        # Create a Python file with some code
        (tmp_path / "src" / "main.py").write_text("""
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
""")

        # Create a file with potential issues
        (tmp_path / "src" / "complex.py").write_text("""
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x + y + z
            elif z < 0:
                return x + y - z
            else:
                return x + y
        elif y < 0:
            return x - y
        else:
            return x
    elif x < 0:
        return -x
    else:
        return 0
""")

        return tmp_path

    def test_cli_version(self) -> None:
        """Test CLI version command."""
        result = subprocess.run(
            [sys.executable, "-m", "archguard", "version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "ArchGuard" in result.stdout

    def test_cli_scan_help(self) -> None:
        """Test scan command help."""
        result = subprocess.run(
            [sys.executable, "-m", "archguard", "scan", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "scan" in result.stdout.lower()

    def test_cli_init_creates_config(self, tmp_path: Path) -> None:
        """Test that init command creates config file."""
        config_path = tmp_path / ".archguard.yml"

        result = subprocess.run(
            [
                sys.executable, "-m", "archguard",
                "init",
                "--path", str(config_path),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert config_path.exists()

        content = config_path.read_text()
        assert "project_name" in content
        assert "detectors:" in content

    def test_cli_scan_finds_files(self, sample_project: Path) -> None:
        """Test that scan finds Python files."""
        result = subprocess.run(
            [
                sys.executable, "-m", "archguard",
                "scan", str(sample_project),
                "--format", "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should find at least 2 Python files
        assert "main.py" in result.stdout or "complex.py" in result.stdout

    def test_cli_scan_json_output(self, sample_project: Path) -> None:
        """Test JSON output format."""
        result = subprocess.run(
            [
                sys.executable, "-m", "archguard",
                "scan", str(sample_project),
                "--format", "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should be valid JSON
        import json
        data = json.loads(result.stdout)
        assert "summary" in data
        assert "results" in data

    def test_cli_scan_with_severity_filter(self, sample_project: Path) -> None:
        """Test scanning with severity filter."""
        result = subprocess.run(
            [
                sys.executable, "-m", "archguard",
                "scan", str(sample_project),
                "--severity", "critical",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_cli_config_show(self, tmp_path: Path) -> None:
        """Test config show command."""
        # First create a config
        config_path = tmp_path / ".archguard.yml"
        config_path.write_text("""
project_name: Test Project
output_format: json
""")

        result = subprocess.run(
            [
                sys.executable, "-m", "archguard",
                "--config", str(config_path),
                "config",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Test Project" in result.stdout or "json" in result.stdout


class TestConfigIntegration:
    """Integration tests for configuration."""

    def test_config_file_loading(self, tmp_path: Path) -> None:
        """Test that config file is loaded correctly."""
        config_path = tmp_path / ".archguard.yml"
        config_path.write_text("""
project_name: Integration Test
output_format: yaml
detectors:
  god_class:
    enabled: false
    severity: high
""")

        # Create a simple Python file
        (tmp_path / "test.py").write_text("x = 1")

        result = subprocess.run(
            [
                sys.executable, "-m", "archguard",
                "--config", str(config_path),
                "scan", str(tmp_path),
                "--format", "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0


class TestHookIntegration:
    """Integration tests for git hooks."""

    def test_hook_installer_exists(self) -> None:
        """Test that hook installer exists."""
        hook_installer = Path(__file__).parent.parent.parent / "hooks" / "install.py"
        assert hook_installer.exists()

    def test_pre_commit_hook_exists(self) -> None:
        """Test that pre-commit hook exists."""
        pre_commit = Path(__file__).parent.parent.parent / "hooks" / "pre-commit"
        assert pre_commit.exists()

    def test_pre_push_hook_exists(self) -> None:
        """Test that pre-push hook exists."""
        pre_push = Path(__file__).parent.parent.parent / "hooks" / "pre-push"
        assert pre_push.exists()


class TestGitHubActionIntegration:
    """Integration tests for GitHub Action."""

    def test_action_yml_exists(self) -> None:
        """Test that action.yml exists."""
        action_yml = Path(__file__).parent.parent.parent / "github-action" / "action.yml"
        assert action_yml.exists()

    def test_action_yml_is_valid(self) -> None:
        """Test that action.yml is valid YAML."""
        import yaml

        action_yml = Path(__file__).parent.parent.parent / "github-action" / "action.yml"
        content = action_yml.read_text()

        data = yaml.safe_load(content)

        assert "name" in data
        assert "description" in data
        assert "runs" in data
