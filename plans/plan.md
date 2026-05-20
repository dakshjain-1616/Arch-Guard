# ArchGuard — AI Code Architecture Drift Detector

## Goal
Build a complete, production-ready Python project that detects architecture degradation patterns in codebases over time, with support for multiple delivery modes (CLI, git hook, GitHub Action).

## Research Summary
- Static analysis tools: `ast` (Python stdlib), `tree-sitter` (multi-language), `radon` (complexity metrics)
- Dependency analysis: `importlib`, `modulegraph`, custom AST traversal
- Configuration: YAML-based rule configuration (PyYAML)
- Git integration: `gitpython` for commit/PR analysis
- CLI framework: `click` or `typer` for modern CLI experience
- Testing: `pytest` with coverage
- Type checking: `mypy` or `pyright`
- Linting: `ruff` (modern, fast replacement for flake8/black)

## Approach

### Architecture Design
1. **Core Engine**: Static analysis framework using Python AST + tree-sitter for multi-language support
2. **Detectors**: Modular detector plugins for each anti-pattern
3. **Configuration**: YAML-based rule configuration with sensible defaults
4. **Git Integration**: PR/commit analysis with delta computation
5. **Reporting**: Multiple output formats (JSON, Markdown, CLI tables)
6. **Delivery**: CLI tool + git hook + GitHub Action

### Subtasks

1. **Project Structure Setup**
   - Create package structure: `archguard/` with subpackages
   - Set up `pyproject.toml` with dependencies and tool configs
   - Create `README.md` skeleton

2. **Core Static Analysis Framework**
   - Implement `archguard/analyzer.py`: Base analyzer class
   - Implement `archguard/parsers/` with Python AST parser
   - Implement dependency graph builder
   - Add file discovery and filtering

3. **Detector Implementations**
   - `CircularDependencyDetector`: Build import graph, detect cycles
   - `GodClassDetector`: Count methods/fields, threshold-based detection
   - `ServiceLayerBypassDetector`: Detect controller→repository/db direct access
   - `MagicValueDetector`: Find hardcoded values that should be constants
   - `CyclomaticComplexityDetector`: Use radon or custom AST visitor
   - `LayerViolationDetector`: Enforce architectural layer import rules

4. **Configuration System**
   - YAML schema for rules and thresholds
   - Config loader with validation
   - Default configuration file

5. **Git Integration & Trend Analysis**
   - PR diff analysis
   - 10-PR trend computation
   - Health delta calculation (improved/degraded/trending)

6. **CLI Implementation**
   - Main CLI with subcommands: `scan`, `trend`, `config`
   - Output formatters: table, json, markdown
   - Exit codes for CI integration

7. **Git Hook Support**
   - Pre-push hook script
   - Installation helper

8. **GitHub Action**
   - `action.yml` metadata
   - Docker-based or composite action
   - Example workflow

9. **Testing Suite**
   - Unit tests for each detector
   - Integration tests for full pipeline
   - Test fixtures with sample code

10. **Tooling Configuration**
    - Ruff for linting/formatting
    - Pyright for type checking
    - Pytest with coverage
    - Pre-commit hooks

11. **Documentation & Diagrams**
    - Complete README with real commands
    - Mermaid architecture diagram
    - Usage examples

## Deliverables

| File Path | Description |
|-----------|-------------|
| `/home/daksh/may20/projects/archguard/pyproject.toml` | Package metadata, dependencies, tool configs |
| `/home/daksh/may20/projects/archguard/archguard/` | Main package directory |
| `/home/daksh/may20/projects/archguard/archguard/__init__.py` | Package init |
| `/home/daksh/may20/projects/archguard/archguard/analyzer.py` | Core analysis engine |
| `/home/daksh/may20/projects/archguard/archguard/detectors/` | All detector implementations |
| `/home/daksh/may20/projects/archguard/archguard/parsers/` | Language parsers |
| `/home/daksh/may20/projects/archguard/archguard/config.py` | Configuration management |
| `/home/daksh/may20/projects/archguard/archguard/git.py` | Git integration |
| `/home/daksh/may20/projects/archguard/archguard/reporters/` | Output formatters |
| `/home/daksh/may20/projects/archguard/archguard/cli.py` | CLI entry point |
| `/home/daksh/may20/projects/archguard/archguard/hooks/` | Git hook scripts |
| `/home/daksh/may20/projects/archguard/action.yml` | GitHub Action definition |
| `/home/daksh/may20/projects/archguard/examples/` | Example configs and workflows |
| `/home/daksh/may20/projects/archguard/tests/` | Test suite |
| `/home/daksh/may20/projects/archguard/README.md` | Complete documentation |
| `/home/daksh/may20/projects/archguard/.pre-commit-hooks.yaml` | Pre-commit hook config |

## Evaluation Criteria
- All 6 detectors functional with real detection logic
- CLI works with `scan`, `trend`, `config` commands
- Git hook installable and functional
- GitHub Action properly configured
- Tests pass with >80% coverage
- Type checking passes
- Linting passes
- README commands are real and runnable
- Architecture diagram accurately reflects implementation

## Notes
- Python 3.10+ required
- No hardcoded secrets
- Model-free core checks (deterministic static analysis)
- Configurable via YAML
- Robust error handling throughout
