#!/usr/bin/env bash
# Install/link the mpy-marketplace into Claude Code settings.
#
# This registers the marketplace as a local directory source so that
# edits to plugin files take effect immediately (next Claude session).
#
# Usage: ./install.sh [--enable-all]
#   --enable-all  Also enable all plugins in the marketplace

set -euo pipefail

MARKETPLACE_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKETPLACE_NAME="mpy-marketplace"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "Marketplace dir: $MARKETPLACE_DIR"

if [ ! -f "$SETTINGS_FILE" ]; then
    echo "Error: $SETTINGS_FILE not found. Is Claude Code installed?"
    exit 1
fi

# Register marketplace in extraKnownMarketplaces
if python3 -c "
import json, sys

settings_path = '$SETTINGS_FILE'
marketplace_name = '$MARKETPLACE_NAME'
marketplace_dir = '$MARKETPLACE_DIR'

with open(settings_path) as f:
    settings = json.load(f)

markets = settings.setdefault('extraKnownMarketplaces', {})

# Check if already registered with same path
existing = markets.get(marketplace_name, {})
existing_path = existing.get('source', {}).get('path', '')
if existing_path == marketplace_dir:
    print(f'{marketplace_name} already registered at {marketplace_dir}')
    sys.exit(0)

markets[marketplace_name] = {
    'source': {
        'source': 'directory',
        'path': marketplace_dir
    }
}

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

print(f'Registered {marketplace_name} -> {marketplace_dir}')
"; then
    echo "Marketplace registration: OK"
else
    echo "Error registering marketplace"
    exit 1
fi

# Enable all plugins and register in installed_plugins.json
if [[ "${1:-}" == "--enable-all" ]]; then
    python3 -c "
import json, os
from datetime import datetime, timezone

settings_path = '$SETTINGS_FILE'
marketplace_name = '$MARKETPLACE_NAME'
marketplace_dir = '$MARKETPLACE_DIR'
installed_path = os.path.join(os.path.dirname(settings_path), 'plugins', 'installed_plugins.json')

with open(settings_path) as f:
    settings = json.load(f)

# Read marketplace.json to find plugin names
mkt_json = f'{marketplace_dir}/.claude-plugin/marketplace.json'
with open(mkt_json) as f:
    mkt = json.load(f)

# Enable plugins in settings
enabled = settings.setdefault('enabledPlugins', {})
for plugin in mkt.get('plugins', []):
    key = f'{plugin[\"name\"]}@{marketplace_name}'
    if key not in enabled:
        enabled[key] = True
        print(f'Enabled: {key}')
    else:
        print(f'Already enabled: {key}')

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

# Register in installed_plugins.json (linked, not cached)
if os.path.exists(installed_path):
    with open(installed_path) as f:
        installed = json.load(f)
else:
    installed = {'version': 2, 'plugins': {}}

now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
for plugin in mkt.get('plugins', []):
    key = f'{plugin[\"name\"]}@{marketplace_name}'
    source_path = os.path.normpath(os.path.join(marketplace_dir, plugin['source']))
    entry = {
        'scope': 'user',
        'installPath': source_path,
        'version': plugin.get('version', '0.1.0'),
        'installedAt': now,
        'lastUpdated': now,
    }
    if key in installed['plugins']:
        # Update path and version in case they changed
        installed['plugins'][key][0]['installPath'] = source_path
        installed['plugins'][key][0]['version'] = plugin.get('version', '0.1.0')
        installed['plugins'][key][0]['lastUpdated'] = now
        print(f'Updated install entry: {key}')
    else:
        installed['plugins'][key] = [entry]
        print(f'Added install entry: {key}')

with open(installed_path, 'w') as f:
    json.dump(installed, f, indent=2)
    f.write('\n')
"
    echo "Plugin enablement: OK"
fi

echo ""
echo "Done. Restart Claude Code to pick up changes."
echo ""
echo "To enable individual plugins later:"
echo "  Add to enabledPlugins in $SETTINGS_FILE:"
echo "  \"plugin-name@$MARKETPLACE_NAME\": true"
