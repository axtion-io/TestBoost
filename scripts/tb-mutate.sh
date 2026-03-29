#!/usr/bin/env bash
# TestBoost - Run mutation testing with PIT and analyze results
# Usage: tb-mutate.sh <project_path> [--target-classes ...] [--target-tests ...] [--min-score N] [--verbose]
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

PROJECT_PATH="${1:?Usage: tb-mutate.sh <project_path> [--target-classes ...] [--min-score N] [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
set +e
python -m testboost mutate "$PROJECT_PATH" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[TESTBOOST_FAILED:exit_code=$EXIT_CODE:step=mutate]"
    echo "CRITICAL: TestBoost command 'mutate' failed. Do NOT proceed with this step manually."
fi

exit $EXIT_CODE
