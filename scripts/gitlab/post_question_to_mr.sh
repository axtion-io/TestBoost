#!/usr/bin/env bash
# Post the pending TestBoost question.json as a MR comment.
#
# Required env (provided by GitLab CI):
#   CI_PROJECT_ID, CI_MERGE_REQUEST_IID, CI_API_V4_URL
#   GITLAB_TOKEN (Project Access Token, scope: api)
#
# Reads the most recent question.json under .testboost/sessions/*/,
# extracts its markdown_preview, and POSTs it as a MR note.
set -euo pipefail

: "${CI_PROJECT_ID:?CI_PROJECT_ID required}"
: "${CI_MERGE_REQUEST_IID:?CI_MERGE_REQUEST_IID required}"
: "${GITLAB_TOKEN:?GITLAB_TOKEN required}"
: "${CI_API_V4_URL:=https://gitlab.com/api/v4}"

# Allow override for tests
SESSION_DIR="${TB_SESSION_DIR:-$(ls -td .testboost/sessions/*/ 2>/dev/null | head -1 || true)}"
if [ -z "$SESSION_DIR" ] || [ ! -d "$SESSION_DIR" ]; then
  echo "No TestBoost session directory found" >&2
  exit 1
fi

QFILE="${SESSION_DIR%/}/question.json"
if [ ! -f "$QFILE" ]; then
  echo "No question.json in $SESSION_DIR" >&2
  exit 1
fi

QID=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['question_id'])" "$QFILE")
PREVIEW=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('markdown_preview',''))" "$QFILE")

# Append a machine-readable marker that the webhook can grep
BODY="${PREVIEW}

<!-- testboost:question_id=${QID} -->"

# Construct request body using jq to escape correctly
PAYLOAD=$(jq -n --arg body "$BODY" '{body: $body}')

# Allow injection of curl for tests
CURL="${TB_CURL_BIN:-curl}"

"$CURL" --fail-with-body -sS -X POST \
  -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  -H "Content-Type: application/json" \
  --data "$PAYLOAD" \
  "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/merge_requests/${CI_MERGE_REQUEST_IID}/notes"

echo "Posted question $QID to MR #$CI_MERGE_REQUEST_IID"
