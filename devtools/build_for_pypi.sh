#!/bin/bash

# Build script for packaging cdflow-cli with scripts for PyPI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$ROOT_DIR"

echo "Syncing runtime scripts to package directory..."
mkdir -p cdflow_cli/scripts
cp scripts/load-secrets.sh cdflow_cli/scripts/

echo "Cleaning previous build artifacts..."
rm -rf dist/ build/ *.egg-info/

echo "Building Python package from $ROOT_DIR..."
python -m build

echo "Build complete! Scripts synced to cdflow_cli/scripts/ and package built."
