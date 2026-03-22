#!/usr/bin/env bash
# Remove the mpy-marketplace registration from Claude Code settings.
#
# This removes the marketplace from extraKnownMarketplaces and disables
# all plugins from this marketplace.

set -euo pipefail

MARKETPLACE_NAME="mpy-marketplace"
SETTINGS_FILE="$HOME/.claude/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    echo "Nothing to do: $SETTINGS_FILE not found"
    exit 0
fi

python3 -c "
import json, os

settings_path = '$SETTINGS_FILE'
marketplace_name = '$MARKETPLACE_NAME'
installed_path = os.path.join(os.path.dirname(settings_path), 'plugins', 'installed_plugins.json')

with open(settings_path) as f:
    settings = json.load(f)

# Remove from extraKnownMarketplaces
markets = settings.get('extraKnownMarketplaces', {})
if marketplace_name in markets:
    del markets[marketplace_name]
    print(f'Removed marketplace: {marketplace_name}')
else:
    print(f'Marketplace not registered: {marketplace_name}')

# Disable plugins from this marketplace
enabled = settings.get('enabledPlugins', {})
to_remove = [k for k in enabled if k.endswith(f'@{marketplace_name}')]
for k in to_remove:
    del enabled[k]
    print(f'Disabled: {k}')

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

# Remove from installed_plugins.json
if os.path.exists(installed_path):
    with open(installed_path) as f:
        installed = json.load(f)
    to_remove = [k for k in installed.get('plugins', {}) if k.endswith(f'@{marketplace_name}')]
    for k in to_remove:
        del installed['plugins'][k]
        print(f'Removed install entry: {k}')
    with open(installed_path, 'w') as f:
        json.dump(installed, f, indent=2)
        f.write('\n')
"

echo ""
echo "Done. Restart Claude Code to pick up changes."
