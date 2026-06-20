#!/usr/bin/env bash
# SessionStart hook for /read-book — one-line status so users know what's wired up.
# Silent when fully ready to avoid spam; points at the installer otherwise.
set -euo pipefail

# Pick a python interpreter: python3 on macOS/Linux, python on Windows.
PY="python3"
command -v python3 >/dev/null 2>&1 || PY="python"

SETUP="${CLAUDE_PLUGIN_ROOT}/scripts/setup.py"

# Fast status probe. setup.py --json prints {unstructured, pandoc, ..., ready}.
status_json="$("$PY" "$SETUP" --json 2>/dev/null || echo '')"

# No python or script failed entirely → tell the user how to bootstrap.
if [[ -z "$status_json" ]]; then
  echo "/read-book: run \`$PY \$CLAUDE_PLUGIN_ROOT/scripts/setup.py\` once to install the unstructured library."
  exit 0
fi

# Ready → silent.
if echo "$status_json" | grep -q '"ready": true'; then
  exit 0
fi

# Not ready → one-line hint.
if echo "$status_json" | grep -q '"unstructured": false'; then
  echo "/read-book: needs the unstructured library. Run \`$PY \$CLAUDE_PLUGIN_ROOT/scripts/setup.py\` once to install."
elif echo "$status_json" | grep -q '"pandoc": false'; then
  echo "/read-book: EPUB support needs pandoc. Run \`$PY \$CLAUDE_PLUGIN_ROOT/scripts/setup.py\` to auto-download it."
else
  echo "/read-book: almost ready — run \`$PY \$CLAUDE_PLUGIN_ROOT/scripts/setup.py\` to finish setup."
fi
