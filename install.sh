#!/usr/bin/env bash
# Install the mpy-marketplace into Claude Code.
#
# Usage: ./install.sh [--enable-all]
#   --enable-all  Also install all plugins from the marketplace

set -euo pipefail

MARKETPLACE_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v claude &>/dev/null; then
    echo "Error: claude CLI not found. Is Claude Code installed?"
    exit 1
fi

echo "Adding marketplace from $MARKETPLACE_DIR..."
claude plugin marketplace add "$MARKETPLACE_DIR"

if [[ "${1:-}" == "--enable-all" ]]; then
    MARKETPLACE_NAME=$(python3 -c "
import json
with open('$MARKETPLACE_DIR/.claude-plugin/marketplace.json') as f:
    print(json.load(f)['name'])
")

    python3 -c "
import json
with open('$MARKETPLACE_DIR/.claude-plugin/marketplace.json') as f:
    mkt = json.load(f)
for p in mkt.get('plugins', []):
    print(p['name'])
" | while read -r plugin; do
        echo "Installing $plugin@$MARKETPLACE_NAME..."
        claude plugin install "$plugin@$MARKETPLACE_NAME" || true
    done
fi

echo ""
echo "Done. Run /reload-plugins in Claude Code to activate."
