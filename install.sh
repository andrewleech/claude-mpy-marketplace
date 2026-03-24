#!/usr/bin/env bash
# Install/link the mpy-marketplace into Claude Code.
#
# Registers the marketplace via `claude plugin marketplace add`, then
# symlinks plugin contents into the cache so edits to source files
# take effect immediately (next Claude session / /reload-plugins).
#
# Usage: ./install.sh [--enable-all]
#   --enable-all  Also enable and symlink all plugins from the marketplace

set -euo pipefail

MARKETPLACE_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS_DIR="$HOME/.claude"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"
INSTALLED_FILE="$SETTINGS_DIR/plugins/installed_plugins.json"

if ! command -v claude &>/dev/null; then
    echo "Error: claude CLI not found. Is Claude Code installed?"
    exit 1
fi

if [ ! -f "$SETTINGS_FILE" ]; then
    echo "Error: $SETTINGS_FILE not found. Is Claude Code configured?"
    exit 1
fi

# Register marketplace using the CLI (handles settings.json manipulation)
echo "Adding marketplace from $MARKETPLACE_DIR..."
claude plugin marketplace add "$MARKETPLACE_DIR"

# Read marketplace name from manifest
MARKETPLACE_NAME=$(python3 -c "
import json
with open('$MARKETPLACE_DIR/.claude-plugin/marketplace.json') as f:
    print(json.load(f)['name'])
")

if [[ "${1:-}" == "--enable-all" ]]; then
    python3 -c "
import json, os, sys
from datetime import datetime, timezone

settings_path = '$SETTINGS_FILE'
marketplace_name = '$MARKETPLACE_NAME'
marketplace_dir = '$MARKETPLACE_DIR'
installed_path = '$INSTALLED_FILE'

# Read marketplace.json
mkt_json = os.path.join(marketplace_dir, '.claude-plugin', 'marketplace.json')
with open(mkt_json) as f:
    mkt = json.load(f)

# Enable plugins in settings.json
with open(settings_path) as f:
    settings = json.load(f)

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

# Create cache symlinks and register in installed_plugins.json
cache_base = os.path.join(os.path.dirname(settings_path), 'plugins', 'cache', marketplace_name)

if os.path.exists(installed_path):
    with open(installed_path) as f:
        installed = json.load(f)
else:
    installed = {'version': 2, 'plugins': {}}

now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
for plugin in mkt.get('plugins', []):
    key = f'{plugin[\"name\"]}@{marketplace_name}'
    version = plugin.get('version', '0.1.0')
    source_path = os.path.normpath(os.path.join(marketplace_dir, plugin['source']))
    cache_dir = os.path.join(cache_base, plugin['name'], version)
    os.makedirs(cache_dir, exist_ok=True)

    # Symlink each top-level item from source into cache
    for item in os.listdir(source_path):
        link = os.path.join(cache_dir, item)
        target = os.path.join(source_path, item)
        if os.path.islink(link):
            os.remove(link)
        elif os.path.isdir(link):
            import shutil
            shutil.rmtree(link)
        elif os.path.exists(link):
            os.remove(link)
        os.symlink(target, link)

    print(f'Symlinked: {source_path} -> {cache_dir}')

    entry = {
        'scope': 'user',
        'installPath': cache_dir,
        'version': version,
        'installedAt': now,
        'lastUpdated': now,
    }
    if key in installed.get('plugins', {}):
        installed['plugins'][key][0]['installPath'] = cache_dir
        installed['plugins'][key][0]['version'] = version
        installed['plugins'][key][0]['lastUpdated'] = now
    else:
        installed.setdefault('plugins', {})[key] = [entry]

with open(installed_path, 'w') as f:
    json.dump(installed, f, indent=2)
    f.write('\n')

print('Plugin symlinks and registration: OK')
"
fi

echo ""
echo "Done. Run /reload-plugins in Claude Code to activate."
