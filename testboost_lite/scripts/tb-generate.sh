#!/usr/bin/env bash
# TestBoost Lite - Generate tests for identified gaps
# Usage: tb-generate.sh <project_path> [--no-llm] [--files file1 file2] [--verbose]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_PATH="${1:?Usage: tb-generate.sh <project_path> [--no-llm] [--files ...] [--verbose]}"
shift

cd "$TESTBOOST_ROOT"
python -m testboost_lite generate "$PROJECT_PATH" "$@"
