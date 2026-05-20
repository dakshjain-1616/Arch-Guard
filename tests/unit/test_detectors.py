"""Unit tests for ArchGuard detectors."""

from __future__ import annotations

from pathlib import Path

from archguard.detectors.circular_dependency import CircularDependencyDetector
from archguard.detectors.cyclomatic_complexity import CyclomaticComplexityDetector
from archguard.detectors.god_class import GodClassDetector
from archguard.detectors.layer_violation import LayerViolationDetector
from archguard.detectors.magic_value import MagicValueDetector
from archguard.detectors.service_layer_bypass import ServiceLayerBypassDetector
from archguard.types import DetectorType


class TestGodClassDetector:
    """Tests for GodClassDetector."""

    def test_detects_class_with_many_methods(self, tmp_path: Path) -> None:
        """Test detection of class with too many methods."""
        code = '''
class BigClass:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass
    def method8(self): pass
    def method9(self): pass
    def method10(self): pass
    def method11(self): pass
    def method12(self): pass
    def method13(self): pass
    def method14(self): pass
    def method15(self): pass
    def method16(self): pass
    def method17(self): pass
    def method18(self): pass
    def method19(self): pass
    def method20(self): pass
    def method21(self): pass
    def method22(self): pass
    def method23(self): pass
    def method24(self): pass
    def method25(self): pass
'''
        detector = GodClassDetector({"max_methods": 20})
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        assert len(result.violations) > 0
        assert result.violations[0].detector_type == DetectorType.GOD_CLASS
        assert "BigClass" in result.violations[0].message

    def test_ignores_small_class(self, tmp_path: Path) -> None:
        """Test that small classes are not flagged."""
        code = '''
class SmallClass:
    def __init__(self):
        self.value = 0
    
    def get_value(self):
        return self.value
    
    def set_value(self, value):
        self.value = value
'''
        detector = GodClassDetector({"max_methods": 20})
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        assert len(result.violations) == 0


class TestCyclomaticComplexityDetector:
    """Tests for CyclomaticComplexityDetector."""

    def test_detects_complex_function(self, tmp_path: Path) -> None:
        """Test detection of function with high complexity."""
        code = '''
def complex_function(x):
    if x > 0:
        if x > 10:
            if x > 100:
                return "big"
            else:
                return "medium"
        else:
            return "small"
    elif x < 0:
        if x < -10:
            return "negative big"
        else:
            return "negative small"
    else:
        return "zero"
'''
        detector = CyclomaticComplexityDetector({"thresholds": {"low": 3}})
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        assert len(result.violations) > 0
        assert result.violations[0].detector_type == DetectorType.CYCLOMATIC_COMPLEXITY

    def test_ignores_simple_function(self, tmp_path: Path) -> None:
        """Test that simple functions are not flagged."""
        code = '''
def simple_function(x):
    if x > 0:
        return "positive"
    return "non-positive"
'''
        detector = CyclomaticComplexityDetector({"thresholds": {"low": 10}})
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        assert len(result.violations) == 0


class TestMagicValueDetector:
    """Tests for MagicValueDetector."""

    def test_detects_magic_number(self, tmp_path: Path) -> None:
        """Test detection of magic numbers."""
        code = '''
def calculate_price(quantity):
    return quantity * 42.50  # Magic number
'''
        detector = MagicValueDetector()
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        # Should find the magic number 42.50
        magic_violations = [v for v in result.violations if "42.50" in v.message]
        assert len(magic_violations) > 0

    def test_ignores_allowed_numbers(self, tmp_path: Path) -> None:
        """Test that allowed numbers are not flagged."""
        code = '''
def process(items):
    if len(items) == 0:
        return None
    if len(items) == 1:
        return items[0]
    return items
'''
        detector = MagicValueDetector()
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        # 0 and 1 are in allowed numbers
        assert len(result.violations) == 0


class TestServiceLayerBypassDetector:
    """Tests for ServiceLayerBypassDetector."""

    def test_detects_repository_import_in_controller(self, tmp_path: Path) -> None:
        """Test detection of repository import in controller."""
        code = '''
from myapp.repositories.user_repository import UserRepository

class UserController:
    def get_user(self, user_id):
        repo = UserRepository()
        return repo.find_by_id(user_id)
'''
        detector = ServiceLayerBypassDetector()
        # Create file in controller directory
        controller_dir = tmp_path / "controllers"
        controller_dir.mkdir()
        file_path = controller_dir / "user_controller.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        # Should detect the repository import
        assert len(result.violations) > 0


class TestLayerViolationDetector:
    """Tests for LayerViolationDetector."""

    def test_detects_layer_violation(self, tmp_path: Path) -> None:
        """Test detection of layer violations."""
        code = '''
# Controller importing from repository (bypassing service)
from myapp.repositories.user_repository import UserRepository

class UserController:
    pass
'''
        detector = LayerViolationDetector()
        controller_dir = tmp_path / "controllers"
        controller_dir.mkdir()
        file_path = controller_dir / "user_controller.py"
        file_path.write_text(code)

        result = detector.analyze(file_path)

        # Should detect the layer violation
        violations = [v for v in result.violations
                     if v.detector_type == DetectorType.LAYER_VIOLATION]
        assert len(violations) > 0


class TestCircularDependencyDetector:
    """Tests for CircularDependencyDetector."""

    def test_requires_project_context(self, tmp_path: Path) -> None:
        """Test that circular dependency detection needs project context."""
        # This detector needs multiple files to detect cycles
        # For unit test, we just verify it runs without error
        code = '''
import module_b

def func_a():
    return module_b.func_b()
'''
        detector = CircularDependencyDetector()
        file_path = tmp_path / "module_a.py"
        file_path.write_text(code)

        # Should not crash
        result = detector.analyze(file_path)

        # Result may or may not have violations depending on project structure
        assert result.file_path == file_path


class TestDetectorConfiguration:
    """Tests for detector configuration."""

    def test_god_class_custom_thresholds(self, tmp_path: Path) -> None:
        """Test custom thresholds for GodClassDetector."""
        code = '''
class MediumClass:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
'''
        # With default threshold (20), this shouldn't trigger
        detector_default = GodClassDetector()
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result_default = detector_default.analyze(file_path)
        assert len(result_default.violations) == 0

        # With custom threshold (5), this should trigger
        detector_custom = GodClassDetector({"max_methods": 5})
        result_custom = detector_custom.analyze(file_path)
        assert len(result_custom.violations) > 0

    def test_complexity_custom_thresholds(self, tmp_path: Path) -> None:
        """Test custom thresholds for CyclomaticComplexityDetector."""
        code = '''
def somewhat_complex(x):
    if x > 0:
        if x > 10:
            return "big"
        return "small"
    return "non-positive"
'''
        # With high threshold, shouldn't trigger
        detector_high = CyclomaticComplexityDetector({"thresholds": {"low": 10}})
        file_path = tmp_path / "test.py"
        file_path.write_text(code)

        result_high = detector_high.analyze(file_path)
        assert len(result_high.violations) == 0

        # With low threshold, should trigger
        detector_low = CyclomaticComplexityDetector({"thresholds": {"low": 2}})
        result_low = detector_low.analyze(file_path)
        assert len(result_low.violations) > 0
