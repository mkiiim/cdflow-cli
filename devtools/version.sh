#!/bin/bash
# Git tagging and versioning script for cdflow-cli
# Usage: ./devtools/version.sh [major|minor|patch] [message]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$ROOT_DIR"

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep -E '^version = ' pyproject.toml | cut -d'"' -f2)
echo "Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# Determine new version based on argument
case "$1" in
    "major")
        NEW_VERSION="$((MAJOR + 1)).0.0"
        ;;
    "minor")
        NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
        ;;
    "patch"|"")
        NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
        ;;
    *)
        echo "Usage: $0 [major|minor|patch] [message]"
        echo "  major: 1.0.1 -> 2.0.0 (breaking changes)"
        echo "  minor: 1.0.1 -> 1.1.0 (new features)"
        echo "  patch: 1.0.1 -> 1.0.2 (bug fixes) [default]"
        exit 1
        ;;
esac

# Get commit message
MESSAGE="${2:-release version $NEW_VERSION}"

echo "New version: $NEW_VERSION"
echo "Tag message: $MESSAGE"

# Confirm with user
read -p "Create tag v$NEW_VERSION? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Update pyproject.toml
sed -i.bak "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
rm pyproject.toml.bak

# Commit version update
git add pyproject.toml
git commit -m "bump version to $NEW_VERSION"

# Create annotated tag
git tag -a "v$NEW_VERSION" -m "$MESSAGE"

echo "✅ Version bumped to $NEW_VERSION"
echo "✅ Tag v$NEW_VERSION created"
echo ""
echo "To push tags to remote:"
echo "  git push origin main --tags"
echo ""
echo "To list all tags:"
echo "  git tag -l"
