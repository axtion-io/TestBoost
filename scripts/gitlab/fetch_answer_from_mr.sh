#!/usr/bin/env bash
# Fetch the developer's answer from the MR and produce a signed answer.json.
#
# Required env:
#   CI_PROJECT_ID, CI_MERGE_REQUEST_IID, CI_API_V4_URL
#   GITLAB_TOKEN (scope: api)
#   TB_OUTPUT (default ./answer.json)
#
# Algorithm:
#   1. Fetch all notes on the MR (newest first).
#   2. For each note authored by an allowed user, look for a fenced JSON
#      block (```json ... ```) followed by `<!-- testboost:question_id=X -->`.
#   3. The note's question_id must match the pending question_id.
#   4. Pipe the raw JSON to `testboost sign-answer` and write to TB_OUTPUT.
set -euo pipefail

: "${CI_PROJECT_ID:?CI_PROJECT_ID required}"
: "${CI_MERGE_REQUEST_IID:?CI_MERGE_REQUEST_IID required}"
: "${GITLAB_TOKEN:?GITLAB_TOKEN required}"
: "${CI_API_V4_URL:=https://gitlab.com/api/v4}"
TB_OUTPUT="${TB_OUTPUT:-./answer.json}"

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
CURL="${TB_CURL_BIN:-curl}"

# Fetch the MR author so we can filter notes
AUTHOR=$("$CURL" --fail-with-body -sS \
  -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/merge_requests/${CI_MERGE_REQUEST_IID}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['author']['username'])")

# Fetch notes (newest first)
NOTES_JSON=$("$CURL" --fail-with-body -sS \
  -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/merge_requests/${CI_MERGE_REQUEST_IID}/notes?per_page=50&order_by=created_at&sort=desc")

# Pick out the first note from the author that references our question_id.
# Write NOTES_JSON to a tmp file rather than interpolating into a heredoc so
# embedded newlines/backticks don't break the Python source.
NOTES_FILE=$(mktemp)
printf '%s' "$NOTES_JSON" > "$NOTES_FILE"

RAW_ANSWER=$(python3 - "$NOTES_FILE" "$QID" "$AUTHOR" <<'PY'
import json, sys, re
notes = json.load(open(sys.argv[1]))
qid, author = sys.argv[2], sys.argv[3]
for n in notes:
    if n.get("system"):
        continue
    if (n.get("author") or {}).get("username") != author:
        continue
    body = n.get("body", "")
    if f"testboost:question_id={qid}" not in body:
        continue
    m = re.search(r"```json\s*\n(.*?)\n```", body, re.DOTALL)
    if not m:
        continue
    try:
        json.loads(m.group(1))
    except Exception:
        continue
    sys.stdout.write(m.group(1))
    sys.exit(0)
sys.exit(2)
PY
)
RC=$?
rm -f "$NOTES_FILE"
if [ "$RC" != "0" ] && [ "$RC" != "2" ]; then
  echo "Failed to parse notes (exit $RC)" >&2
  exit "$RC"
fi
if [ -z "$RAW_ANSWER" ]; then
  echo "No matching answer found in MR comments (author=$AUTHOR, qid=$QID)" >&2
  exit 2
fi

# Write the raw answer to a tmp file and call testboost sign-answer
RAW_FILE=$(mktemp)
printf '%s' "$RAW_ANSWER" > "$RAW_FILE"
poetry run python -m testboost sign-answer "$CI_PROJECT_DIR" \
  --question-file "$QFILE" \
  --answer-file "$RAW_FILE" \
  --output "$TB_OUTPUT"

rm -f "$RAW_FILE"
echo "Signed answer written to $TB_OUTPUT"
