#!/usr/bin/env bash
# TestBoost Lite - Compile and validate generated tests
# Usage: tb-validate.sh <project_path> [--verbose]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_PATH="${1:?Usage: tb-validate.sh <project_path> [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
python -m testboost_lite validate "$PROJECT_PATH" "$@"
