#!/bin/bash
# Development-only script to load secrets from files into environment variables
# Usage: source ./scripts/load-secrets.sh [nb-secrets-file]
# 
# WARNING: This script is for development convenience only.
# Never use in production. Never commit secrets files.

NB_SECRETS_FILE="${1:-config/dev-secrets.env}"
NB_SECRETS_DIR="$(dirname "$NB_SECRETS_FILE")"

# Check NationBuilder secrets file
if [ ! -f "$NB_SECRETS_FILE" ]; then
    echo "ERROR: NationBuilder secrets file not found: $NB_SECRETS_FILE"
    echo "Create a file with format:"
    echo "  NB_SLUG=your-org"
    echo "  NB_CLIENT_ID=your-id" 
    echo "  NB_CLIENT_SECRET=your-secret"
    return 1 2>/dev/null || exit 1
fi

echo "Loading secrets from:"
echo "  NB secrets: $NB_SECRETS_FILE"

# Export each line as environment variable
set -a  # Automatically export variables
source "$NB_SECRETS_FILE"
set +a  # Stop auto-export

echo "✅ Loaded secrets:"
echo "   NB_CONFIG_NAME=${NB_CONFIG_NAME}"
echo "   NB_SLUG=${NB_SLUG}"
echo "   NB_CLIENT_ID=${NB_CLIENT_ID:0:10}..."
echo "   NB_CLIENT_SECRET=***hidden***"