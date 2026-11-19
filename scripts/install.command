#!/bin/zsh
# Installs this checkout only. No model download, API call or Lightroom access.
set -euo pipefail
cd "${0:A:h:h}"

if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 was not found. Install Python 3.11 or later, then try again.' >&2
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11 or later is required.")'
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo 'Node.js and npm were not found. Install a compatible version listed in README.md, then try again.' >&2
  exit 1
fi
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (!(major > 22 || (major === 22 && minor >= 12) || (major === 20 && minor >= 19))) { console.error("Node.js 20.19+ in the 20 series, or 22.12 or later, is required."); process.exit(1); }'
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
if [[ ! -x .venv/bin/python ]]; then
  echo 'The .venv folder exists but does not contain a valid environment. Rename it manually and try again.' >&2
  exit 1
fi
.venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "The .venv environment requires Python 3.11 or later: rename it and try again.")'

echo 'Installing Python dependencies in this project’s .venv environment…'
.venv/bin/python -m pip install -e .
echo 'Installing and building the web interface…'
npm --prefix web ci
npm --prefix web run build

echo ''
echo 'Installation complete.'
echo 'Run scripts/start.command and leave the backend window open.'
echo 'Then add plugin/lrc-photo-selection.lrplugin in Lightroom Plug-in Manager.'
echo 'No models were downloaded, no analysis was started and no catalog was opened.'
