# Verification Transcript - ArchGuard

Date (UTC): 2026-05-20
Project root: `/home/daksh/may20/projects/archguard`

## Environment and install
1. `python -m pip install -e '.[dev]'`
- Result: **FAIL** (`python: command not found`)

2. `python3 -m pip install -e '.[dev]'`
- Result: **FAIL** (PEP 668 externally-managed environment)

3. `./venv/bin/python -m pip install -e '.[dev]'`
- Result: **PASS**

## Quality gates
4. `./venv/bin/ruff check src/ tests/`
- Initial result: **FAIL** (large lint backlog)
- Final result after fixes: **PASS**

5. `./venv/bin/pyright src/`
- Initial result: **FAIL** (type issues across CLI/detectors/config/git)
- Final result after fixes: **PASS** (`0 errors`)

6. `./venv/bin/pytest`
- Initial result: **FAIL** (2 failing tests)
- Final result after fixes: **PASS** (`79 passed`)

## CLI verification
7. `./venv/bin/archguard --help`
- Result: **PASS**

8. `./venv/bin/archguard scan --help`
- Result: **PASS**

9. `./venv/bin/archguard trend --help`
- Result: **PASS**

10. `./venv/bin/archguard init --help`
- Result: **PASS**

11. `./venv/bin/archguard config --help`
- Result: **PASS**

12. `./venv/bin/archguard version`
- Result: **PASS**

13. `./venv/bin/archguard init --path <tmp>/.archguard.yml`
- Result: **PASS** (config created)

14. `./venv/bin/archguard --config <tmp>/.archguard.yml config`
- Result: **PASS**

15. `./venv/bin/archguard --config <tmp>/.archguard.yml config output_format`
- Result: **PASS**

16. `./venv/bin/archguard --config <tmp>/.archguard.yml config output_format json`
- Result: **PASS**

17. `./venv/bin/archguard scan src --format json`
- Result: **PASS** (valid JSON output)

18. `./venv/bin/archguard trend --commits 2 --format json` (run inside a temporary initialized git repo)
- Result: **PASS**

## README command truthfulness
- Verified and corrected CLI docs to reflect actual command structure: `--config` is a global option (before subcommand), not a `scan`-specific flag.

