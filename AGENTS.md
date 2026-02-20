# Repository Guidelines

## Project Structure

- **Entry point**: `main.py`
- **Package**: `python_project_template/` (create when adding first module)
- **Tests**: `tests/` mirroring package structure
- **Config**: `pyproject.toml` (metadata, dependencies, tools)
- **Automation**: `Makefile` (common tasks)
- **Ignore**: `.gitignore` covers `.venv`, caches, etc.

## Commands

- `make setup` — Install Python 3.14 via `uv`, create `.venv`, install dependencies
- `make run` — Run `main.py` in virtualenv
- `make tidy` — Format code and sort imports (run before commits)
- `make lint` — Auto-fix with `ruff`, then type check with `ty`
- `make clean` — Remove virtualenv, lockfiles, caches

## Development Workflow

After editing code:
1. `make tidy` — Format and sort imports
2. `make lint` — Fix issues and type check

## Code Style

- **Format**: `ruff` defaults (4 spaces, 120 chars, double quotes, isort imports)
- **Naming**: `snake_case` (modules, functions, vars), `UpperCamelCase` (classes), `UPPER_SNAKE` (constants)
- **Imports**: Prefer explicit relative imports within package
- **Types**: Annotations encouraged; validated by `ty`

## Testing

- Create `tests/` with `__init__.py`
- Mirror module layout (`tests/test_main.py`, etc.)
- Use `unittest` (standard library) or add `pytest` later
- Name tests: `test_<behavior>`
- Run: `uv run python -m unittest` (or `pytest` if adopted)
- Target: 80%+ line coverage for new modules

## Commits & PRs

**Commits**:
- Imperative mood: `Add run target`, `Fix lint errors`
- Reference issues in body when applicable

**Pull Requests**:
- Summary of changes
- Testing evidence (commands/screenshots)
- Follow-up tasks
- Breaking changes (if any)
- Request review after `make lint` passes and tests green
