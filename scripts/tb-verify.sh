#!/usr/bin/env bash
# TestBoost - Verify an integrity token
# Usage: tb-verify.sh <project_path> <token>
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

PROJECT_PATH="${1:?Usage: tb-verify.sh <project_path> <token>}"
TOKEN="${2:?Usage: tb-verify.sh <project_path> <token>}"

cd "$TESTBOOST_ROOT"
python -m testboost verify "$PROJECT_PATH" "$TOKEN"
