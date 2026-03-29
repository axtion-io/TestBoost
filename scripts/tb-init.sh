#!/usr/bin/env bash
# TestBoost - Initialize a test generation session
# Usage: tb-init.sh <project_path> [--name <name>] [--description <desc>]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Activate virtual environment
if [ -f "$TESTBOOST_ROOT/.venv/Scripts/activate" ]; then
    source "$TESTBOOST_ROOT/.venv/Scripts/activate"
elif [ -f "$TESTBOOST_ROOT/.venv/bin/activate" ]; then
    source "$TESTBOOST_ROOT/.venv/bin/activate"
elif [ -f "$TESTBOOST_ROOT/venv/bin/activate" ]; then
    source "$TESTBOOST_ROOT/venv/bin/activate"
fi

PROJECT_PATH="${1:?Usage: tb-init.sh <project_path> [--name <name>] [--description <desc>]}"
shift

cd "$TESTBOOST_ROOT"
set +e
python -m testboost init "$PROJECT_PATH" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[TESTBOOST_FAILED:exit_code=$EXIT_CODE:step=init]"
    echo "CRITICAL: TestBoost command 'init' failed. Do NOT proceed with this step manually."
fi

exit $EXIT_CODE
