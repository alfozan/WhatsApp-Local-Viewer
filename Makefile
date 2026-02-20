# Makefile for setting up Python environment with uv

# Default target
.DEFAULT_GOAL := setup

# setup python virtual environment and dependencies
setup: clean
	@echo ">>> Installing Python..."
	uv python install

	@echo ">>> Creating virtual environment..."
	uv venv .venv

	# ignore .venv folder in cloud-sync (e.g. Dropbox)
	xattr -w 'com.apple.fileprovider.ignore#P' 1 .venv

	@echo ">>> Activating virtual environment..."
	. .venv/bin/activate

	@echo ">>> Installing dependencies..."
	uv sync --upgrade
	uv lock --upgrade

	@echo ">>> Python version..."
	uv run python --version

clean:
	@echo ">>> Cleaning up project..."
	rm -rf .venv > /dev/null 2>&1
	rm -rf uv.lock

	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	rm -rf .ruff_cache

run:
	uv run python main.py

lint:
	@echo ">>> Linting with Ruff..."
	@uv run ruff check . --fix --no-cache
	@echo ">>> Type checking with ty..."
	@uv run ty check

tidy:
	# Tidy Python, shell, and JSON files
	@echo ">>> Tidying Python files..."
	@uv run ruff check --fix --extend-ignore ALL --select I001 . --no-cache
	@uv run ruff format . --no-cache
	@echo ">>> Tidying shell scripts..."
	@find . -name '*.sh' -print0 | xargs -0 -r uv run beautysh --indent-size 2 --force-function-style fnpar
	@echo ">>> Tidying JSON files..."
	@find . -name '*.json' -print0 | xargs -0 -I {} uv run python -m json.tool --indent 4 {} {}
