#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
if [[ ! -x .venv/bin/lrc-selection || ! -f web/dist/index.html ]]; then
  echo 'Installation incomplete. Follow README.md to create the Python environment and build the web app.'
  exit 1
fi
exec .venv/bin/lrc-selection
