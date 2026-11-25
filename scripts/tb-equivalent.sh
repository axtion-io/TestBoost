#!/usr/bin/env bash
# TestBoost - Declare surviving mutants equivalent (no test can observe them), list or withdraw
# Usage: tb-equivalent.sh <project_path> [<id> ...] [--reason "..."] [--remove]
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

PROJECT_PATH="${1:?Usage: tb-equivalent.sh <project_path> [<id> ...] [--reason ...] [--remove]}"
shift

if [ ! -d "$PROJECT_PATH" ]; then
    echo "Error: project path not found: $PROJECT_PATH" >&2
    exit 1
fi
PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"

cd "$TESTBOOST_ROOT"
set +e
python -m testboost equivalent "$PROJECT_PATH" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[TESTBOOST_FAILED:exit_code=$EXIT_CODE:step=equivalent]"
    echo "CRITICAL: TestBoost command 'equivalent' failed. Do NOT proceed with this step manually."
fi

exit $EXIT_CODE
