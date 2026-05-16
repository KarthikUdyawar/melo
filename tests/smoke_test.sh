#!/usr/bin/env bash
# =============================================================================
# smoke_test.sh — Melo end-to-end smoke test
#
# Covers:
#   /health
#   POST /songs/preview  (META-2)
#   POST /songs + poll   (full ingest pipeline)
#   GET  /songs/{id}/stream
#   POST/DELETE/GET /favorites  (LIB-1)
#   Validation error paths (422, 404)
#
# Usage:
#   chmod +x tests/smoke_test.sh
#   ./tests/smoke_test.sh
#   ./tests/smoke_test.sh --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
#   API_URL=http://localhost:8000 ./tests/smoke_test.sh
#
# Requirements: curl, jq
# =============================================================================

set -euo pipefail

API="${API_URL:-http://localhost:8000}"
YT_URL=""
DEFAULT_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url)
            [[ $# -ge 2 ]] || { echo "Missing value for --url"; exit 1; }
            YT_URL="$2"
            shift 2
            ;;
        *) shift ;;
    esac
done
YT_URL="${YT_URL:-$DEFAULT_URL}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass()    { echo -e "${GREEN}  ✓ $1${NC}"; }
fail()    { echo -e "${RED}  ✗ $1${NC}"; exit 1; }
info()    { echo -e "${CYAN}  → $1${NC}"; }
warn()    { echo -e "${YELLOW}  ! $1${NC}"; }
section() { echo -e "\n${CYAN}══ $1 ══${NC}"; }

api_get() {
    curl -sf --max-time 15 "${API}$1"
}

api_get_raw() {
    curl -s --max-time 15 -w "|||%{http_code}" "${API}$1"
}

api_post() {
    curl -sf --max-time 15 -X POST \
        -H "Content-Type: application/json" \
        -d "$2" \
        "${API}$1"
}

api_post_raw() {
    curl -s --max-time 15 -X POST \
        -H "Content-Type: application/json" \
        -d "$2" \
        -w "|||%{http_code}" \
        "${API}$1"
}

api_delete_raw() {
    curl -s --max-time 15 -X DELETE -w "|||%{http_code}" "${API}$1"
}

# =============================================================================
# S1. Health
# =============================================================================
section "S1. Health check"

HEALTH=$(api_get "/health") || fail "GET /health failed"
STATUS=$(echo "$HEALTH" | jq -r '.status')
[[ "$STATUS" == "ok" ]] || fail "Health status: $STATUS (expected ok)"
pass "GET /health → ok"

# =============================================================================
# S2. Preview — happy path
# =============================================================================
section "S2. Preview — happy path"

PREVIEW=$(api_post "/songs/preview" "{\"url\": \"$YT_URL\"}") \
    || fail "POST /songs/preview failed"

HTTP_CODE=$(echo "$PREVIEW" | jq -r '.status_code')
[[ "$HTTP_CODE" == "200" ]] || fail "Expected status_code=200, got $HTTP_CODE"

YOUTUBE_ID=$(echo "$PREVIEW" | jq -r '.body.youtube_id')
[[ -n "$YOUTUBE_ID" && "$YOUTUBE_ID" != "null" ]] \
    || fail "youtube_id missing from preview response"

TITLE=$(echo "$PREVIEW"    | jq -r '.body.title        // "null"')
DURATION=$(echo "$PREVIEW" | jq -r '.body.duration     // "null"')
CHANNEL=$(echo "$PREVIEW"  | jq -r '.body.channel      // "null"')
UPLOAD_DATE=$(echo "$PREVIEW" | jq -r '.body.upload_date // "null"')
THUMBNAIL=$(echo "$PREVIEW" | jq -r '.body.thumbnail_url // "null"')

pass "POST /songs/preview → 200"
info "youtube_id:   $YOUTUBE_ID"
info "title:        $TITLE"
info "duration:     ${DURATION}s"
info "channel:      $CHANNEL"
info "upload_date:  $UPLOAD_DATE"
info "thumbnail:    $THUMBNAIL"

MESSAGE=$(echo "$PREVIEW" | jq -r '.message')
[[ "$MESSAGE" != "null" && -n "$MESSAGE" ]] || fail "envelope.message missing"
pass "Envelope shape valid (status_code, message, body)"

if [[ "$DURATION" != "null" ]]; then
    jq -ne --argjson d "$DURATION" '$d > 0' >/dev/null \
        || fail "duration must be > 0, got $DURATION"
    pass "duration > 0"
fi

# =============================================================================
# S3. Preview — stateless (no DB write)
# =============================================================================
section "S3. Preview — stateless"

BEFORE=$(api_get "/songs" | jq -r '.body.count')
api_post "/songs/preview" "{\"url\": \"$YT_URL\"}" > /dev/null
AFTER=$(api_get "/songs" | jq -r '.body.count')

[[ "$BEFORE" == "$AFTER" ]] \
    || fail "Song count changed after preview: $BEFORE → $AFTER (DB write!)"
pass "Song count unchanged ($BEFORE → $AFTER) — no DB write"

# =============================================================================
# S4. Preview — URL variants
# =============================================================================
section "S4. Preview — URL format variants"

for TEST_URL in \
    "https://www.youtube.com/shorts/dQw4w9WgXcQ" \
    "https://youtu.be/dQw4w9WgXcQ"; do
    RESP=$(api_post "/songs/preview" "{\"url\": \"$TEST_URL\"}") \
        || fail "preview failed for $TEST_URL"
    CODE=$(echo "$RESP" | jq -r '.status_code')
    [[ "$CODE" == "200" ]] || fail "Expected 200 for $TEST_URL, got $CODE"
    pass "$(echo "$TEST_URL" | sed 's|https://||') → 200"
done

# =============================================================================
# S5. Preview — validation errors
# =============================================================================
section "S5. Preview — validation errors"

RAW=$(api_post_raw "/songs/preview" '{"url": "https://vimeo.com/123456"}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Non-YouTube URL: expected 422, got $HTTP"
pass "Non-YouTube URL → 422"

RAW=$(api_post_raw "/songs/preview" '{}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Missing url: expected 422, got $HTTP"
pass "Missing url field → 422"

RAW=$(api_post_raw "/songs/preview" '{"url": "https://www.youtube.com/"}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "YT homepage: expected 422, got $HTTP"
pass "YouTube homepage (no video ID) → 422"

# =============================================================================
# S6. Ingest — POST /songs + poll
# =============================================================================
section "S6. Ingest — POST /songs"

BASELINE=$(api_get "/songs" | jq -r '.body.count')

SONG_RESP=$(api_post "/songs" "{\"url\": \"$YT_URL\"}") \
    || fail "POST /songs failed"
HTTP_STATUS=$(echo "$SONG_RESP" | jq -r '.status_code')
[[ "$HTTP_STATUS" == "202" ]] || fail "Expected 202, got $HTTP_STATUS"

SONG_ID=$(echo "$SONG_RESP" | jq -r '.body.id')
[[ -n "$SONG_ID" && "$SONG_ID" != "null" ]] || fail "No song id in response"
pass "POST /songs → 202, id=$SONG_ID"

# =============================================================================
# S7. Poll until done
# =============================================================================
section "S7. Poll until status=done"

TIMEOUT=120
ELAPSED=0
STATUS="pending"

while [[ "$STATUS" != "done" && $ELAPSED -lt $TIMEOUT ]]; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    SONG=$(api_get "/songs/$SONG_ID") || fail "GET /songs/$SONG_ID failed"
    STATUS=$(echo "$SONG" | jq -r '.body.status')
    info "[$ELAPSED s] status=$STATUS"
    [[ "$STATUS" == "failed" ]] && fail "Song processing failed"
done

[[ "$STATUS" == "done" ]] || fail "Song not done after ${TIMEOUT}s (status=$STATUS)"
pass "Song done in ${ELAPSED}s"

# =============================================================================
# S8. Stream
# =============================================================================
section "S8. Stream — GET /songs/{id}/stream"

STREAM_RAW=$(curl -s --max-time 30 -w "|||%{http_code}|||%{size_download}" \
    "${API}/songs/${SONG_ID}/stream" -o /dev/null)
HTTP="${STREAM_RAW%%|||*}"
REST="${STREAM_RAW#*|||}"
STREAM_HTTP="${REST%%|||*}"
BYTES="${REST##*|||}"

[[ "$STREAM_HTTP" == "200" ]] || fail "Stream: expected 200, got $STREAM_HTTP"
[[ "$BYTES" -gt 1000 ]] || fail "Stream response too small: ${BYTES} bytes"
pass "GET /songs/{id}/stream → 200, ${BYTES} bytes"

# =============================================================================
# S9. Favorites — lifecycle
# =============================================================================
section "S9. Favorites — lifecycle"

# POST → 201
FAV_RAW=$(api_post_raw "/favorites/$SONG_ID" '{}')
FAV_BODY="${FAV_RAW%|||*}"
FAV_HTTP="${FAV_RAW##*|||}"
[[ "$FAV_HTTP" == "201" ]] || fail "POST /favorites/$SONG_ID: expected 201, got $FAV_HTTP"
FAV_SONG_ID=$(echo "$FAV_BODY" | jq -r '.body.song_id')
[[ "$FAV_SONG_ID" == "$SONG_ID" ]] || fail "song_id mismatch in favorite response"
pass "POST /favorites/{id} → 201"

# POST again → 200 (idempotent)
FAV_RAW2=$(api_post_raw "/favorites/$SONG_ID" '{}')
FAV_HTTP2="${FAV_RAW2##*|||}"
[[ "$FAV_HTTP2" == "200" ]] || fail "Second POST /favorites: expected 200, got $FAV_HTTP2"
pass "POST /favorites/{id} again → 200 (idempotent)"

# GET /favorites — appears in list
FAVS=$(api_get "/favorites") || fail "GET /favorites failed"
FAV_COUNT=$(echo "$FAVS" | jq -r '.body.count')
[[ "$FAV_COUNT" -ge 1 ]] || fail "Expected ≥1 favorite, got $FAV_COUNT"
IS_FAV=$(echo "$FAVS" | jq -r --arg id "$SONG_ID" '.body.records[] | select(.id==$id) | .is_favorite')
[[ "$IS_FAV" == "true" ]] || fail "Song not marked is_favorite=true in GET /favorites"
pass "GET /favorites → count=$FAV_COUNT, is_favorite=true"

# GET /songs — is_favorite reflected
SONGS=$(api_get "/songs") || fail "GET /songs failed"
IS_FAV_SONGS=$(echo "$SONGS" | jq -r --arg id "$SONG_ID" '.body.records[] | select(.id==$id) | .is_favorite')
[[ "$IS_FAV_SONGS" == "true" ]] || fail "is_favorite not true in GET /songs"
pass "GET /songs — is_favorite=true reflected"

# DELETE → 204
DEL_RAW=$(api_delete_raw "/favorites/$SONG_ID")
DEL_HTTP="${DEL_RAW##*|||}"
[[ "$DEL_HTTP" == "204" ]] || fail "DELETE /favorites: expected 204, got $DEL_HTTP"
pass "DELETE /favorites/{id} → 204"

# GET /favorites after delete — gone
FAVS_AFTER=$(api_get "/favorites") || fail "GET /favorites after delete failed"
COUNT_AFTER=$(echo "$FAVS_AFTER" | jq -r '.body.count')
[[ "$COUNT_AFTER" -eq 0 ]] || warn "Expected 0 favorites after delete, got $COUNT_AFTER (may have pre-existing)"
pass "GET /favorites after delete → count=$COUNT_AFTER"

# is_favorite=false in /songs after delete
SONGS_AFTER=$(api_get "/songs") || fail "GET /songs after delete failed"
IS_FAV_AFTER=$(echo "$SONGS_AFTER" | jq -r --arg id "$SONG_ID" '.body.records[] | select(.id==$id) | .is_favorite')
[[ "$IS_FAV_AFTER" == "false" ]] || fail "is_favorite still true after DELETE"
pass "GET /songs — is_favorite=false after delete"

# =============================================================================
# S10. Favorites — error paths
# =============================================================================
section "S10. Favorites — error paths"

FAKE_ID="00000000-0000-0000-0000-000000000000"

RAW=$(api_post_raw "/favorites/$FAKE_ID" '{}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "POST /favorites/unknown: expected 404, got $HTTP"
pass "POST /favorites/{unknown_id} → 404"

RAW=$(api_delete_raw "/favorites/$FAKE_ID")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "DELETE /favorites/unknown: expected 404, got $HTTP"
pass "DELETE /favorites/{unknown_id} → 404"

RAW=$(api_delete_raw "/favorites/$SONG_ID")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "DELETE /favorites/not-favorited: expected 404, got $HTTP"
pass "DELETE /favorites/{not-favorited} → 404"

# =============================================================================
# S11. Validation — songs
# =============================================================================
section "S11. Songs — validation errors"

RAW=$(api_post_raw "/songs" '{"url": "https://vimeo.com/123"}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Bad URL: expected 422, got $HTTP"
pass "POST /songs bad URL → 422"

RAW=$(api_post_raw "/songs" "{\"url\": \"$YT_URL\", \"speed\": 10.0}")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Bad speed: expected 422, got $HTTP"
pass "POST /songs bad speed → 422"

RAW=$(api_get_raw "/songs/00000000-0000-0000-0000-000000000000")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "Unknown song: expected 404, got $HTTP"
pass "GET /songs/{unknown} → 404"

# =============================================================================
# S12. Song count increased
# =============================================================================
section "S12. Song count increased"

FINAL=$(api_get "/songs" | jq -r '.body.count')
[[ "$FINAL" -gt "$BASELINE" ]] \
    || fail "Song count did not increase: baseline=$BASELINE final=$FINAL"
pass "Song count: $BASELINE → $FINAL"

# =============================================================================
# Summary
# =============================================================================
echo -e "\n${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ All smoke tests passed! (12 sections)${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}\n"
