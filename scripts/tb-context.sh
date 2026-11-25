#!/usr/bin/env bash
# TestBoost - Agent mode: write one generation prompt per gap (or per surviving-mutant class with --killer)
# Usage: tb-context.sh <project_path> [--files ...] [--killer] [--verbose]
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

PROJECT_PATH="${1:?Usage: tb-context.sh <project_path> [--files ...] [--verbose]}"
shift

if [ ! -d "$PROJECT_PATH" ]; then
    echo "Error: project path not found: $PROJECT_PATH" >&2
    exit 1
fi
PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"

cd "$TESTBOOST_ROOT"
set +e
python -m testboost context "$PROJECT_PATH" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[TESTBOOST_FAILED:exit_code=$EXIT_CODE:step=context]"
    echo "CRITICAL: TestBoost command 'context' failed. Do NOT proceed with this step manually."
fi

exit $EXIT_CODE
