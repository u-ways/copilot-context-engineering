# The only command surface for this repository. CI calls these same recipes.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List recipes
default:
    @just --list

# Install the locked environment with every dependency group
install:
    uv sync --locked --all-groups

# Format code and apply safe lint fixes
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Check formatting and lint rules
lint:
    uv run ruff format --check .
    uv run ruff check .

# Static type checking (strict)
typecheck:
    uv run mypy

# Run the offline test suite
test *ARGS:
    uv run pytest {{ ARGS }}

# Run the offline test suite with branch coverage (terminal + XML report)
cov:
    uv run pytest --cov --cov-report=term --cov-report=xml

# Run the end-to-end tier against the real pinned upstream repository (network)
e2e *ARGS:
    uv run pytest -m e2e {{ ARGS }}

# Run the LLM-backed scenario checks with a runtime: copilot or claude (network, real agent, paid)
llm RUNTIME *ARGS:
    uv run pytest -m llm --runtime {{ RUNTIME }} {{ ARGS }}

# Audit locked dependencies for known vulnerabilities
audit:
    uv export --format requirements-txt --all-groups --no-emit-project --output-file requirements-audit.txt
    uvx pip-audit --strict --disable-pip --requirement requirements-audit.txt

# The CI quality and test jobs: lint, typecheck, coverage (CI also runs audit and smoke)
check: lint typecheck cov

# Run the CLI from the development environment
run *ARGS:
    uv run cce {{ ARGS }}

# Print the version after checking pyproject.toml and src/cce/__init__.py agree
version:
    #!/usr/bin/env bash
    set -euo pipefail
    py="$(sed -nE 's/^version = "([^"]+)"$/\1/p' pyproject.toml)"
    init="$(sed -nE 's/^__version__ = "([^"]+)"$/\1/p' src/cce/__init__.py)"
    if [ -z "$py" ] || [ "$py" != "$init" ]; then
        echo "version mismatch: pyproject.toml='$py' src/cce/__init__.py='$init'" >&2
        exit 1
    fi
    echo "$py"

# Install the tool as a user would and exercise the CLI end to end
smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    export CCE_WORKSPACE="${CCE_WORKSPACE:-$(mktemp -d)}"
    uv tool install --force --reinstall .
    export PATH="$(uv tool dir --bin):$PATH"
    cce --help
    cce version
    cce doctor --offline
    cce guide 01 > /dev/null
    cce guide presenting > /dev/null
    cce setup
    cce list
    cce reset all
    cce teardown

# Render the developer slide deck to dist/slides.html (needs npx)
slides:
    npx -y @marp-team/marp-cli@4 docs/slides.md --theme docs/slides-theme.css -o dist/slides.html

# Remove caches, build output and generated reports
clean:
    rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml requirements-audit.txt dist build
