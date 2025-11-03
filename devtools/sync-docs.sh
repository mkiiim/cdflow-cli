#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

# Sync root files to docs directory
# This ensures LICENSE and CLA.md copies in docs/ stay current

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Syncing root files to docs directory..."

# Copy LICENSE to docs/license.md
if [ -f "$REPO_ROOT/LICENSE" ]; then
    cp "$REPO_ROOT/LICENSE" "$REPO_ROOT/docs/license.md"
    echo "✓ LICENSE → docs/license.md"
else
    echo "✗ LICENSE not found"
    exit 1
fi

# Copy CLA.md to docs/cla.md
if [ -f "$REPO_ROOT/CLA.md" ]; then
    cp "$REPO_ROOT/CLA.md" "$REPO_ROOT/docs/cla.md"
    echo "✓ CLA.md → docs/cla.md"
else
    echo "✗ CLA.md not found"
    exit 1
fi

echo "✓ All files synced successfully"
