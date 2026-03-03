#!/usr/bin/env bash
# TestBoost Lite - Analyze project structure and test context
# Usage: tb-analyze.sh <project_path> [--verbose]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_PATH="${1:?Usage: tb-analyze.sh <project_path> [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
python -m testboost_lite analyze "$PROJECT_PATH" "$@"
