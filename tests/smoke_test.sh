#!/usr/bin/env bash
# =============================================================================
# smoke_preview.sh — POST /songs/preview smoke test (META-2)
#
# Standalone: ./smoke_preview.sh
# Or inline into smoke_test.sh between section 2 and section 3.
#
# Usage:
#   chmod +x smoke_preview.sh
#   ./smoke_preview.sh
#   ./smoke_preview.sh --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
#
# Requirements: curl, jq
# =============================================================================

set -euo pipefail

API="${API_URL:-http://localhost:8000}"
YT_URL="${1:-}"
DEFAULT_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url) YT_URL="$2"; shift 2 ;;
        *) shift ;;
    esac
done
YT_URL="${YT_URL:-$DEFAULT_URL}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${GREEN}  ✓ $1${NC}"; }
fail() { echo -e "${RED}  ✗ $1${NC}"; exit 1; }
info() { echo -e "${CYAN}  → $1${NC}"; }
section() { echo -e "\n${CYAN}══ $1 ══${NC}"; }

api_post() {
    curl -sf --max-time 15 -X POST \
        -H "Content-Type: application/json" \
        -d "$2" \
        "${API}$1"
}

api_post_raw() {
    # Returns HTTP status + body separated by |||
    curl -s --max-time 15 -X POST \
        -H "Content-Type: application/json" \
        -d "$2" \
        -w "|||%{http_code}" \
        "${API}$1"
}

# ── P1. Happy path ─────────────────────────────────────────────────────────────
section "P1. Preview — happy path"

PREVIEW=$(api_post "/songs/preview" "{\"url\": \"$YT_URL\"}") \
    || fail "POST /songs/preview failed"

HTTP_CODE=$(echo "$PREVIEW" | jq -r '.status_code')
[[ "$HTTP_CODE" == "200" ]] || fail "Expected status_code=200, got $HTTP_CODE"

YOUTUBE_ID=$(echo "$PREVIEW" | jq -r '.body.youtube_id')
[[ -n "$YOUTUBE_ID" && "$YOUTUBE_ID" != "null" ]] \
    || fail "youtube_id missing from response"

TITLE=$(echo "$PREVIEW" | jq -r '.body.title // "null"')
DURATION=$(echo "$PREVIEW" | jq -r '.body.duration // "null"')
CHANNEL=$(echo "$PREVIEW" | jq -r '.body.channel // "null"')
UPLOAD_DATE=$(echo "$PREVIEW" | jq -r '.body.upload_date // "null"')
THUMBNAIL=$(echo "$PREVIEW" | jq -r '.body.thumbnail_url // "null"')

pass "POST /songs/preview → 200"
info "youtube_id:   $YOUTUBE_ID"
info "title:        $TITLE"
info "duration:     ${DURATION}s"
info "channel:      $CHANNEL"
info "upload_date:  $UPLOAD_DATE"
info "thumbnail:    $THUMBNAIL"

# Envelope shape
MESSAGE=$(echo "$PREVIEW" | jq -r '.message')
[[ "$MESSAGE" != "null" && -n "$MESSAGE" ]] || fail "envelope.message missing"
pass "Envelope shape valid (status_code, message, body)"

# duration > 0
if [[ "$DURATION" != "null" ]]; then
    python3 -c "assert float('$DURATION') > 0" 2>/dev/null \
        || fail "duration must be > 0, got $DURATION"
    pass "duration > 0"
fi

# ── P2. No DB row created ─────────────────────────────────────────────────────
section "P2. Preview — stateless (no DB write)"

# Compare song count before/after
BEFORE=$(curl -sf --max-time 10 "${API}/songs" | jq -r '.body.count')
api_post "/songs/preview" "{\"url\": \"$YT_URL\"}" > /dev/null
AFTER=$(curl -sf --max-time 10 "${API}/songs" | jq -r '.body.count')

[[ "$BEFORE" == "$AFTER" ]] \
    || fail "Song count changed after preview: $BEFORE → $AFTER (DB write detected!)"
pass "Song count unchanged ($BEFORE → $AFTER) — no DB write"

# ── P3. URL format variants ───────────────────────────────────────────────────
section "P3. Preview — URL format variants"

SHORTS_URL="https://www.youtube.com/shorts/dQw4w9WgXcQ"
YOUTU_BE_URL="https://youtu.be/dQw4w9WgXcQ"

for TEST_URL in "$SHORTS_URL" "$YOUTU_BE_URL"; do
    RESP=$(api_post "/songs/preview" "{\"url\": \"$TEST_URL\"}") \
        || fail "preview failed for $TEST_URL"
    CODE=$(echo "$RESP" | jq -r '.status_code')
    [[ "$CODE" == "200" ]] || fail "Expected 200 for $TEST_URL, got $CODE"
    pass "$(echo "$TEST_URL" | sed 's|https://||') → 200"
done

# ── P4. Validation — bad URL ──────────────────────────────────────────────────
section "P4. Preview — invalid URL → 422"

RAW=$(api_post_raw "/songs/preview" '{"url": "https://vimeo.com/123456"}')
BODY="${RAW%|||*}"
HTTP="${RAW##*|||}"

[[ "$HTTP" == "422" ]] || fail "Expected 422 for non-YouTube URL, got $HTTP"
BODY_NULL=$(echo "$BODY" | jq -r '.body')
[[ "$BODY_NULL" == "null" ]] || fail "Expected body=null on 422, got $BODY_NULL"
pass "Non-YouTube URL → 422 with body: null"

# ── P5. Validation — missing url field ───────────────────────────────────────
section "P5. Preview — missing url field → 422"

RAW=$(api_post_raw "/songs/preview" '{}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Expected 422 for missing url, got $HTTP"
pass "Missing url field → 422"

# ── P6. Validation — YouTube homepage (no video ID) ──────────────────────────
section "P6. Preview — YouTube homepage → 422"

RAW=$(api_post_raw "/songs/preview" '{"url": "https://www.youtube.com/"}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Expected 422 for YouTube homepage, got $HTTP"
pass "YouTube homepage (no video ID) → 422"

# ── P7. Idempotency ───────────────────────────────────────────────────────────
section "P7. Preview — idempotency (3 calls, 0 rows)"

COUNT_BEFORE=$(curl -sf --max-time 10 "${API}/songs" | jq -r '.body.count')
for i in 1 2 3; do
    api_post "/songs/preview" "{\"url\": \"$YT_URL\"}" > /dev/null
done
COUNT_AFTER=$(curl -sf --max-time 10 "${API}/songs" | jq -r '.body.count')

[[ "$COUNT_BEFORE" == "$COUNT_AFTER" ]] \
    || fail "Song count changed after 3 previews: $COUNT_BEFORE → $COUNT_AFTER"
pass "3x preview calls → count still $COUNT_AFTER (idempotent)"

# ── Summary ───────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}══════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ All preview smoke tests passed!${NC}"
echo -e "${GREEN}══════════════════════════════════${NC}\n"
