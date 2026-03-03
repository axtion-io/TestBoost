#!/usr/bin/env bash
# TestBoost Lite - Show current session status
# Usage: tb-status.sh <project_path>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBOOST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROJECT_PATH="${1:?Usage: tb-status.sh <project_path>}"

cd "$TESTBOOST_ROOT"
python -m testboost_lite status "$PROJECT_PATH"
