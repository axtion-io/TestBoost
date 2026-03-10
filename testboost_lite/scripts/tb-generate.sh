#!/usr/bin/env bash
# TestBoost Lite - Generate tests for identified gaps
# Usage: tb-generate.sh <project_path> [--files file1 file2] [--verbose]
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

PROJECT_PATH="${1:?Usage: tb-generate.sh <project_path> [--files ...] [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
set +e
python -m testboost_lite generate "$PROJECT_PATH" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[TESTBOOST_FAILED:exit_code=$EXIT_CODE:step=generate]"
    echo "CRITICAL: TestBoost command 'generate' failed. Do NOT proceed with this step manually."
fi

exit $EXIT_CODE
