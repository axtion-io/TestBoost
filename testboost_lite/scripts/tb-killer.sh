#!/usr/bin/env bash
# TestBoost Lite - Generate killer tests for surviving mutants
# Usage: tb-killer.sh <project_path> [--max-tests N] [--verbose]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Activate virtual environment
if [ -f "$TESTBOOST_ROOT/.venv/Scripts/activate" ]; then
    source "$TESTBOOST_ROOT/.venv/Scripts/activate"
elif [ -f "$TESTBOOST_ROOT/.venv/bin/activate" ]; then
    source "$TESTBOOST_ROOT/.venv/bin/activate"
elif [ -f "$TESTBOOST_ROOT/venv/bin/activate" ]; then
    source "$TESTBOOST_ROOT/venv/bin/activate"
fi

PROJECT_PATH="${1:?Usage: tb-killer.sh <project_path> [--max-tests N] [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
set +e
python -m testboost_lite killer "$PROJECT_PATH" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[TESTBOOST_FAILED:exit_code=$EXIT_CODE:step=killer]"
    echo "CRITICAL: TestBoost command 'killer' failed. Do NOT proceed with this step manually."
fi

exit $EXIT_CODE
