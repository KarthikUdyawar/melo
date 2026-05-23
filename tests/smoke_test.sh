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
#   POST/GET/DELETE /playlists  (LIB-2)
#   GET /songs filtering, sorting, pagination (API-2)
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

FAV_RAW=$(api_post_raw "/favorites/$SONG_ID" '{}')
FAV_BODY="${FAV_RAW%|||*}"
FAV_HTTP="${FAV_RAW##*|||}"
[[ "$FAV_HTTP" == "201" ]] || fail "POST /favorites/$SONG_ID: expected 201, got $FAV_HTTP"
FAV_SONG_ID=$(echo "$FAV_BODY" | jq -r '.body.song_id')
[[ "$FAV_SONG_ID" == "$SONG_ID" ]] || fail "song_id mismatch in favorite response"
pass "POST /favorites/{id} → 201"

FAV_RAW2=$(api_post_raw "/favorites/$SONG_ID" '{}')
FAV_HTTP2="${FAV_RAW2##*|||}"
[[ "$FAV_HTTP2" == "200" ]] || fail "Second POST /favorites: expected 200, got $FAV_HTTP2"
pass "POST /favorites/{id} again → 200 (idempotent)"

FAVS=$(api_get "/favorites") || fail "GET /favorites failed"
FAV_COUNT=$(echo "$FAVS" | jq -r '.body.count')
[[ "$FAV_COUNT" -ge 1 ]] || fail "Expected ≥1 favorite, got $FAV_COUNT"
IS_FAV=$(echo "$FAVS" | jq -r --arg id "$SONG_ID" '.body.records[] | select(.id==$id) | .is_favorite')
[[ "$IS_FAV" == "true" ]] || fail "Song not marked is_favorite=true in GET /favorites"
pass "GET /favorites → count=$FAV_COUNT, is_favorite=true"

SONG_ONE=$(api_get "/songs/$SONG_ID") || fail "GET /songs/$SONG_ID failed"
IS_FAV_SONG=$(echo "$SONG_ONE" | jq -r '.body.is_favorite')
[[ "$IS_FAV_SONG" == "true" ]] || fail "is_favorite not true in GET /songs/{id}"
pass "GET /songs/{id} — is_favorite=true reflected"

DEL_RAW=$(api_delete_raw "/favorites/$SONG_ID")
DEL_HTTP="${DEL_RAW##*|||}"
[[ "$DEL_HTTP" == "204" ]] || fail "DELETE /favorites: expected 204, got $DEL_HTTP"
pass "DELETE /favorites/{id} → 204"

FAVS_AFTER=$(api_get "/favorites") || fail "GET /favorites after delete failed"
COUNT_AFTER=$(echo "$FAVS_AFTER" | jq -r '.body.count')
[[ "$COUNT_AFTER" -eq 0 ]] || warn "Expected 0 favorites after delete, got $COUNT_AFTER (may have pre-existing)"
IS_PRESENT_AFTER=$(echo "$FAVS_AFTER" | jq -r --arg id "$SONG_ID" '[.body.records[] | select(.id==$id)] | length')
[[ "$IS_PRESENT_AFTER" -eq 0 ]] || fail "Deleted song still present in GET /favorites"
pass "GET /favorites after delete → count=$COUNT_AFTER"

SONG_ONE_AFTER=$(api_get "/songs/$SONG_ID") || fail "GET /songs/$SONG_ID after delete failed"
IS_FAV_AFTER=$(echo "$SONG_ONE_AFTER" | jq -r '.body.is_favorite')
[[ "$IS_FAV_AFTER" == "false" ]] || fail "is_favorite still true after DELETE"
pass "GET /songs/{id} — is_favorite=false after delete"

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
# S13. Playlists — create
# =============================================================================
section "S13. Playlists — create"

PL_RESP=$(api_post "/playlists" '{"name": "Smoke Test Playlist"}') \
    || fail "POST /playlists failed"
PL_CODE=$(echo "$PL_RESP" | jq -r '.status_code')
[[ "$PL_CODE" == "201" ]] || fail "Expected 201, got $PL_CODE"

PLAYLIST_ID=$(echo "$PL_RESP" | jq -r '.body.id')
PL_NAME=$(echo "$PL_RESP" | jq -r '.body.name')
PL_COUNT=$(echo "$PL_RESP" | jq -r '.body.song_count // (.body.songs | length)')
[[ -n "$PLAYLIST_ID" && "$PLAYLIST_ID" != "null" ]] || fail "No playlist id in response"
[[ "$PL_NAME" == "Smoke Test Playlist" ]] || fail "name mismatch: $PL_NAME"
[[ "$PL_COUNT" == "0" ]] || fail "Expected song_count=0, got $PL_COUNT"
pass "POST /playlists → 201, id=$PLAYLIST_ID"

RAW=$(api_post_raw "/playlists" '{"name": ""}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Empty name: expected 422, got $HTTP"
pass "POST /playlists empty name → 422"

RAW=$(api_post_raw "/playlists" '{}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Missing name: expected 422, got $HTTP"
pass "POST /playlists missing name → 422"

# =============================================================================
# S14. Playlists — list
# =============================================================================
section "S14. Playlists — list"

PL_LIST=$(api_get "/playlists") || fail "GET /playlists failed"
PL_LIST_COUNT=$(echo "$PL_LIST" | jq -r '.body.count')
[[ "$PL_LIST_COUNT" -ge 1 ]] || fail "Expected ≥1 playlist, got $PL_LIST_COUNT"
PL_FOUND=$(echo "$PL_LIST" | jq -r --arg id "$PLAYLIST_ID" '[.body.records[] | select(.id==$id)] | length')
[[ "$PL_FOUND" -eq 1 ]] || fail "Created playlist not found in GET /playlists"
pass "GET /playlists → count=$PL_LIST_COUNT, playlist present"

# =============================================================================
# S15. Playlists — add song
# =============================================================================
section "S15. Playlists — add song"

ADD_RAW=$(api_post_raw "/playlists/$PLAYLIST_ID/songs/$SONG_ID" '{}')
ADD_BODY="${ADD_RAW%|||*}"
ADD_HTTP="${ADD_RAW##*|||}"
[[ "$ADD_HTTP" == "201" ]] || fail "POST /playlists/{id}/songs/{sid}: expected 201, got $ADD_HTTP"
ADD_SONG_COUNT=$(echo "$ADD_BODY" | jq -r '.body.song_count')
[[ "$ADD_SONG_COUNT" == "1" ]] || fail "Expected song_count=1 after add, got $ADD_SONG_COUNT"
pass "POST /playlists/{id}/songs/{song_id} → 201, song_count=1"

ADD_RAW2=$(api_post_raw "/playlists/$PLAYLIST_ID/songs/$SONG_ID" '{}')
ADD_HTTP2="${ADD_RAW2##*|||}"
[[ "$ADD_HTTP2" == "200" ]] || fail "Second add: expected 200, got $ADD_HTTP2"
pass "POST /playlists/{id}/songs/{song_id} again → 200 (idempotent)"

RAW=$(api_post_raw "/playlists/00000000-0000-0000-0000-000000000000/songs/$SONG_ID" '{}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "Unknown playlist add: expected 404, got $HTTP"
pass "POST /playlists/{unknown}/songs/{song_id} → 404"

RAW=$(api_post_raw "/playlists/$PLAYLIST_ID/songs/00000000-0000-0000-0000-000000000000" '{}')
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "Unknown song add: expected 404, got $HTTP"
pass "POST /playlists/{id}/songs/{unknown} → 404"

# =============================================================================
# S16. Playlists — get detail
# =============================================================================
section "S16. Playlists — get detail"

PL_DETAIL=$(api_get "/playlists/$PLAYLIST_ID") || fail "GET /playlists/$PLAYLIST_ID failed"
PL_DETAIL_NAME=$(echo "$PL_DETAIL" | jq -r '.body.name')
PL_SONGS=$(echo "$PL_DETAIL" | jq -r '.body.songs | length')
PL_SONG_ID=$(echo "$PL_DETAIL" | jq -r '.body.songs[0].id')

[[ "$PL_DETAIL_NAME" == "Smoke Test Playlist" ]] || fail "name mismatch in detail: $PL_DETAIL_NAME"
[[ "$PL_SONGS" -eq 1 ]] || fail "Expected 1 song in playlist, got $PL_SONGS"
[[ "$PL_SONG_ID" == "$SONG_ID" ]] || fail "song id mismatch in playlist detail"
pass "GET /playlists/{id} → name ok, 1 song, song_id matches"

HAS_IS_FAV=$(echo "$PL_DETAIL" | jq -r '.body.songs[0] | has("is_favorite")')
[[ "$HAS_IS_FAV" == "true" ]] || fail "Song in playlist missing is_favorite field"
pass "Songs in playlist detail have is_favorite field"

RAW=$(api_get_raw "/playlists/00000000-0000-0000-0000-000000000000")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "GET /playlists/unknown: expected 404, got $HTTP"
pass "GET /playlists/{unknown} → 404"

# =============================================================================
# S17. Playlists — remove song
# =============================================================================
section "S17. Playlists — remove song"

DEL_SONG_RAW=$(api_delete_raw "/playlists/$PLAYLIST_ID/songs/$SONG_ID")
DEL_SONG_HTTP="${DEL_SONG_RAW##*|||}"
[[ "$DEL_SONG_HTTP" == "204" ]] || fail "DELETE /playlists/{id}/songs/{sid}: expected 204, got $DEL_SONG_HTTP"
pass "DELETE /playlists/{id}/songs/{song_id} → 204"

PL_AFTER_REMOVE=$(api_get "/playlists/$PLAYLIST_ID") || fail "GET /playlists after remove failed"
SONGS_AFTER=$(echo "$PL_AFTER_REMOVE" | jq -r '.body.songs | length')
[[ "$SONGS_AFTER" -eq 0 ]] || fail "Expected 0 songs after remove, got $SONGS_AFTER"
pass "Song removed from playlist detail"

RAW=$(api_delete_raw "/playlists/$PLAYLIST_ID/songs/$SONG_ID")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "Remove not-in-playlist: expected 404, got $HTTP"
pass "DELETE /playlists/{id}/songs/{not-in-playlist} → 404"

# =============================================================================
# S18. Playlists — delete playlist
# =============================================================================
section "S18. Playlists — delete playlist"

api_post "/playlists/$PLAYLIST_ID/songs/$SONG_ID" '{}' > /dev/null

DEL_PL_RAW=$(api_delete_raw "/playlists/$PLAYLIST_ID")
DEL_PL_HTTP="${DEL_PL_RAW##*|||}"
[[ "$DEL_PL_HTTP" == "204" ]] || fail "DELETE /playlists/{id}: expected 204, got $DEL_PL_HTTP"
pass "DELETE /playlists/{id} → 204"

RAW=$(api_get_raw "/playlists/$PLAYLIST_ID")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "GET deleted playlist: expected 404, got $HTTP"
pass "GET /playlists/{deleted} → 404"

PL_LIST_AFTER=$(api_get "/playlists") || fail "GET /playlists after delete failed"
PL_STILL_THERE=$(echo "$PL_LIST_AFTER" | jq -r --arg id "$PLAYLIST_ID" '[.body.records[] | select(.id==$id)] | length')
[[ "$PL_STILL_THERE" -eq 0 ]] || fail "Deleted playlist still in GET /playlists"
pass "Deleted playlist absent from GET /playlists"

RAW=$(api_delete_raw "/playlists/00000000-0000-0000-0000-000000000000")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "404" ]] || fail "DELETE /playlists/unknown: expected 404, got $HTTP"
pass "DELETE /playlists/{unknown} → 404"

# =============================================================================
# S19. Playlists — same song in multiple playlists
# =============================================================================
section "S19. Playlists — same song in multiple playlists"

PL_A=$(api_post "/playlists" '{"name": "Playlist A"}' | jq -r '.body.id') \
    || fail "Create playlist A failed"
PL_B=$(api_post "/playlists" '{"name": "Playlist B"}' | jq -r '.body.id') \
    || fail "Create playlist B failed"

api_post "/playlists/$PL_A/songs/$SONG_ID" '{}' > /dev/null
api_post "/playlists/$PL_B/songs/$SONG_ID" '{}' > /dev/null

SONGS_A=$(api_get "/playlists/$PL_A" | jq -r '.body.songs | length')
SONGS_B=$(api_get "/playlists/$PL_B" | jq -r '.body.songs | length')
[[ "$SONGS_A" -eq 1 ]] || fail "Playlist A: expected 1 song, got $SONGS_A"
[[ "$SONGS_B" -eq 1 ]] || fail "Playlist B: expected 1 song, got $SONGS_B"
pass "Same song added to two playlists successfully"

api_delete_raw "/playlists/$PL_A/songs/$SONG_ID" > /dev/null
SONGS_A_AFTER=$(api_get "/playlists/$PL_A" | jq -r '.body.songs | length')
SONGS_B_AFTER=$(api_get "/playlists/$PL_B" | jq -r '.body.songs | length')
[[ "$SONGS_A_AFTER" -eq 0 ]] || fail "Playlist A: expected 0 songs after delete, got $SONGS_A_AFTER"
[[ "$SONGS_B_AFTER" -eq 1 ]] || fail "Playlist B: expected 1 song still, got $SONGS_B_AFTER"
pass "Delete from one playlist leaves other intact"

api_delete_raw "/playlists/$PL_A" > /dev/null
api_delete_raw "/playlists/$PL_B" > /dev/null

# =============================================================================
# S20. GET /songs — status filter
# =============================================================================
section "S20. GET /songs — status filter"

DONE_RESP=$(api_get "/songs?status=done") || fail "GET /songs?status=done failed"
DONE_RECORDS=$(echo "$DONE_RESP" | jq -r '.body.records')
DONE_COUNT=$(echo "$DONE_RESP" | jq -r '.body.count')
[[ "$DONE_COUNT" -ge 1 ]] || fail "Expected ≥1 done song, got $DONE_COUNT"
ALL_DONE=$(echo "$DONE_RECORDS" | jq -r '[.[].status == "done"] | all')
[[ "$ALL_DONE" == "true" ]] || fail "Non-done songs returned with status=done filter"
pass "GET /songs?status=done → count=$DONE_COUNT, all records done"

RAW=$(api_get_raw "/songs?status=bogus")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Invalid status: expected 422, got $HTTP"
pass "GET /songs?status=bogus → 422"

# =============================================================================
# S21. GET /songs — search filter
# =============================================================================
section "S21. GET /songs — search filter"

if [[ "$TITLE" != "null" && -n "$TITLE" ]]; then
    SEARCH_TERM=$(echo "$TITLE" | cut -c1-4 | tr '[:upper:]' '[:lower:]')
    SEARCH_RESP=$(api_get "/songs?search=$SEARCH_TERM") || fail "GET /songs?search= failed"
    SEARCH_COUNT=$(echo "$SEARCH_RESP" | jq -r '.body.count')
    [[ "$SEARCH_COUNT" -ge 1 ]] || fail "Search for '$SEARCH_TERM' returned 0 results"
    pass "GET /songs?search=$SEARCH_TERM → $SEARCH_COUNT result(s)"
else
    warn "Skipping search test — title was null in preview"
fi

NO_MATCH=$(api_get "/songs?search=zzznomatch_xyz") || fail "GET /songs?search=zzz failed"
NO_COUNT=$(echo "$NO_MATCH" | jq -r '.body.count')
[[ "$NO_COUNT" -eq 0 ]] || fail "Expected 0 for no-match search, got $NO_COUNT"
pass "GET /songs?search=zzznomatch_xyz → 0 results"

# =============================================================================
# S22. GET /songs — favorite filter
# =============================================================================
section "S22. GET /songs — favorite filter"

api_post "/favorites/$SONG_ID" '{}' > /dev/null

FAV_FILTER=$(api_get "/songs?favorite=true") || fail "GET /songs?favorite=true failed"
FAV_COUNT=$(echo "$FAV_FILTER" | jq -r '.body.count')
[[ "$FAV_COUNT" -ge 1 ]] || fail "Expected ≥1 favorited song, got $FAV_COUNT"
ALL_IS_FAV=$(echo "$FAV_FILTER" | jq -r '[.body.records[].is_favorite] | all')
[[ "$ALL_IS_FAV" == "true" ]] || fail "Not all records have is_favorite=true"
pass "GET /songs?favorite=true → count=$FAV_COUNT, all is_favorite=true"

NON_FAV=$(api_get "/songs?favorite=false") || fail "GET /songs?favorite=false failed"
SONG_IN_NON_FAV=$(echo "$NON_FAV" | jq -r --arg id "$SONG_ID" '[.body.records[] | select(.id == $id)] | length')
[[ "$SONG_IN_NON_FAV" -eq 0 ]] || fail "Favorited song appears in favorite=false results"
pass "GET /songs?favorite=false → favorited song excluded"

RAW=$(api_get_raw "/songs?favorite=maybe")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Invalid favorite param: expected 422, got $HTTP"
pass "GET /songs?favorite=maybe → 422"

api_delete_raw "/favorites/$SONG_ID" > /dev/null

# =============================================================================
# S23. GET /songs — sort_by + order
# =============================================================================
section "S23. GET /songs — sort_by + order"

SORTED=$(api_get "/songs?sort_by=created_at&order=asc") || fail "GET /songs?sort_by=created_at&order=asc failed"
TIMESTAMPS=$(echo "$SORTED" | jq -r '[.body.records[].created_at]')
IS_SORTED=$(echo "$TIMESTAMPS" | jq -r '. == (. | sort)')
[[ "$IS_SORTED" == "true" ]] || fail "Records not sorted ascending by created_at"
pass "GET /songs?sort_by=created_at&order=asc → records sorted asc"

RAW=$(api_get_raw "/songs?sort_by=invalid_field")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Invalid sort_by: expected 422, got $HTTP"
pass "GET /songs?sort_by=invalid_field → 422"

RAW=$(api_get_raw "/songs?order=sideways")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "Invalid order: expected 422, got $HTTP"
pass "GET /songs?order=sideways → 422"

# =============================================================================
# S24. GET /songs — pagination + bookmark cursor
# =============================================================================
section "S24. GET /songs — pagination + bookmark cursor"

PAGE1=$(api_get "/songs?sort_by=created_at&order=asc&limit=1") || fail "GET /songs?limit=1 failed"
P1_COUNT=$(echo "$PAGE1" | jq -r '.body.count')
P1_RECORDS=$(echo "$PAGE1" | jq -r '.body.records | length')
P1_BOOKMARK=$(echo "$PAGE1" | jq -r '.body.bookmark')

[[ "$P1_RECORDS" -eq 1 ]] || fail "limit=1: expected 1 record, got $P1_RECORDS"
[[ "$P1_COUNT" -ge 1 ]] || fail "count should reflect total, got $P1_COUNT"
[[ "$P1_BOOKMARK" != "null" && -n "$P1_BOOKMARK" ]] || fail "bookmark missing on page 1"
pass "GET /songs?limit=1 → 1 record, count=$P1_COUNT, bookmark present"

if [[ "$P1_COUNT" -ge 2 ]]; then
    PAGE2=$(api_get "/songs?sort_by=created_at&order=asc&limit=1&after=$P1_BOOKMARK") \
        || fail "GET /songs?after=<bookmark> failed"
    P2_RECORDS=$(echo "$PAGE2" | jq -r '.body.records | length')
    P2_ID=$(echo "$PAGE2" | jq -r '.body.records[0].id')
    P1_ID=$(echo "$PAGE1" | jq -r '.body.records[0].id')
    [[ "$P2_RECORDS" -eq 1 ]] || fail "Page 2: expected 1 record, got $P2_RECORDS"
    [[ "$P2_ID" != "$P1_ID" ]] || fail "Page 2 returned same record as page 1"
    pass "GET /songs?after=<bookmark> → different record on page 2"
else
    warn "Only 1 song in DB — skipping cursor page-2 test"
fi

RAW=$(api_get_raw "/songs?limit=9999")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "limit=9999: expected 422, got $HTTP"
pass "GET /songs?limit=9999 → 422 (exceeds max)"

RAW=$(api_get_raw "/songs?offset=-1")
HTTP="${RAW##*|||}"
[[ "$HTTP" == "422" ]] || fail "offset=-1: expected 422, got $HTTP"
pass "GET /songs?offset=-1 → 422"

# =============================================================================
# Summary
# =============================================================================
echo -e "\n${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ All smoke tests passed! (24 sections)${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}\n"
