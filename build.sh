#!/usr/bin/env bash
# Build the single-file icbc-control-panel executable.
#
# Run on each target platform (Linux / macOS / Windows-via-WSL doesn't count —
# Windows users need to build on actual Windows).
#
# First time setup:
#   python3 -m venv .venv-build
#   .venv-build/bin/pip install pyinstaller -r requirements.txt
#
# Then:
#   ./build.sh

set -euo pipefail

cd "$(dirname "$0")"

if [[ -x .venv-build/bin/pyinstaller ]]; then
    PYI=.venv-build/bin/pyinstaller
elif command -v pyinstaller >/dev/null 2>&1; then
    PYI=pyinstaller
else
    echo "❌ pyinstaller not found. Run:"
    echo "   python3 -m venv .venv-build"
    echo "   .venv-build/bin/pip install pyinstaller -r requirements.txt"
    exit 1
fi

rm -rf build dist
"$PYI" icbc-control-panel.spec --noconfirm

echo
echo "✅ Built: dist/icbc-control-panel"
ls -lh dist/icbc-control-panel
