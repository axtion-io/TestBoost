#!/usr/bin/env bash
# TestBoost Lite - Compile and validate generated tests
# Usage: tb-validate.sh <project_path> [--verbose]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Activate virtual environment
if [ -f "$TESTBOOST_ROOT/.venv/Scripts/activate" ]; then
    source "$TESTBOOST_ROOT/.venv/Scripts/activate"
elif [ -f "$TESTBOOST_ROOT/venv/bin/activate" ]; then
    source "$TESTBOOST_ROOT/venv/bin/activate"
fi

PROJECT_PATH="${1:?Usage: tb-validate.sh <project_path> [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
python -m testboost_lite validate "$PROJECT_PATH" "$@"
