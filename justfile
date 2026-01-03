# justfile — canonical Python project tasks
#
# Usage:
#   just                # list commands
#   just venv           # create .venv (first time) + install deps
#   just deps           # reinstall deps after requirements.txt changes
#   just devdeps        # reinstall deps after requirements-dev.txt changes
#   just rebuild        # delete .venv and recreate from scratch
#   just test           # run tests (pytest)
#   just lint           # flake8 lint
#   just format         # black format
#   just format-check  # black check (no changes)
#   just clean          # remove caches/build artifacts

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set dotenv-load := true

# ---- Config ----
PYTHON := "python3"
VENV := ".venv"
BIN := VENV + "/bin"
PIP := BIN + "/pip"
PY := BIN + "/python"
REQ := "requirements.txt"
DEVREQ := "requirements-dev.txt"

# Default: show available recipes
default:
    @just --list

# ---- Environment / Dependencies ----

# Install/update runtime deps
deps:
    @test -x "{{PIP}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @test -f "{{REQ}}" || (echo "Missing {{REQ}}" && exit 1)
    @{{PIP}} install -r {{REQ}}

# Install/update dev deps (includes runtime deps via -r requirements.txt)
devdeps:
    @test -x "{{PIP}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @test -f "{{DEVREQ}}" || (echo "Missing {{DEVREQ}}" && exit 1)
    @{{PIP}} install -r {{DEVREQ}}

# Create venv + install dev deps (default local dev setup)
venv:
    @if [ ! -x "{{PIP}}" ]; then \
      echo "Creating venv at {{VENV}}"; \
      {{PYTHON}} -m venv {{VENV}}; \
    else \
      echo "Updating venv at {{VENV}}"; \
    fi
    @{{PIP}} install -U pip setuptools wheel
    @{{PIP}} install -r {{DEVREQ}}
    @echo ""
    @echo "✅ Venv created/updated at: {{VENV}}"
    @echo "To activate in THIS shell:"
    @echo "  source {{VENV}}/bin/activate"

# Blow away venv and recreate from scratch
rebuild:
    @rm -rf {{VENV}}
    @just venv

# Write out the exact installed packages
freeze:
    @test -x "{{PIP}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @{{PIP}} freeze

# ---- Quality / Tests ----

test *args="":
    @test -x "{{PY}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @{{PY}} -m pytest {{args}}

lint:
    @test -x "{{PY}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @{{PY}} -m flake8 .

format:
    @test -x "{{PY}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @{{PY}} -m black .

format-check:
    @test -x "{{PY}}" || (echo "Missing venv. Run: just venv" && exit 1)
    @{{PY}} -m black --check .

# ---- Housekeeping ----

clean:
    @rm -rf .pytest_cache .mypy_cache
    @find . -type d -name "__pycache__" -prune -exec rm -rf {} +
    @rm -rf build dist *.egg-info