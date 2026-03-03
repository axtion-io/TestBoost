#!/usr/bin/env bash
# TestBoost Lite - Initialize a test generation session
# Usage: tb-init.sh <project_path> [--name <name>] [--description <desc>]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_PATH="${1:?Usage: tb-init.sh <project_path> [--name <name>] [--description <desc>]}"
shift

cd "$TESTBOOST_ROOT"
python -m testboost_lite init "$PROJECT_PATH" "$@"
