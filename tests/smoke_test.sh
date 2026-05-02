#!/usr/bin/env bash
# =============================================================================
# smoke_test.sh — Melo end-to-end smoke test (Docker)
#
# Usage:
#   chmod +x smoke_test.sh
#   ./smoke_test.sh
#   ./smoke_test.sh --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
#
# Requirements: curl, jq
# =============================================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
API="${API_URL:-http://localhost:8000}"
YT_URL="${1:-}"
DEFAULT_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
POLL_INTERVAL=3
POLL_TIMEOUT=120  # seconds to wait for processing

# Parse --url flag
while [[ $# -gt 0 ]]; do
    case "$1" in
        --url) YT_URL="$2"; shift 2 ;;
        *) shift ;;
    esac
done
YT_URL="${YT_URL:-$DEFAULT_URL}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${GREEN}  ✓ $1${NC}"; }
fail() { echo -e "${RED}  ✗ $1${NC}"; exit 1; }
info() { echo -e "${CYAN}▶ $1${NC}"; }
warn() { echo -e "${YELLOW}  ! $1${NC}"; }
section() { echo -e "\n${CYAN}══ $1 ══${NC}"; }

# ── Helpers ───────────────────────────────────────────────────────────────────
require() {
    command -v "$1" &>/dev/null || fail "Required tool not found: $1 (install it first)"
}

api_get() {
    curl -sf --max-time 10 "${API}$1"
}

api_post() {
    curl -sf --max-time 10 -X POST \
        -H "Content-Type: application/json" \
        -d "$2" \
        "${API}$1"
}

# ── Preflight ─────────────────────────────────────────────────────────────────
section "Preflight"
require curl
require jq

echo "  API:     $API"
echo "  YT URL:  $YT_URL"

# ── 1. Health check ───────────────────────────────────────────────────────────
section "1. Health"
HEALTH=$(api_get "/health") || fail "Health endpoint unreachable — is Docker running? (make up)"
STATUS=$(echo "$HEALTH" | jq -r '.status // .body.status // "ok"')
pass "GET /health → $STATUS"

# ── 2. List songs (baseline) ──────────────────────────────────────────────────
section "2. List Songs (baseline)"
LIST=$(api_get "/songs") || fail "GET /songs failed"
INITIAL_COUNT=$(echo "$LIST" | jq -r '.body.count')
pass "GET /songs → $INITIAL_COUNT songs"

# ── 3. Submit song ────────────────────────────────────────────────────────────
section "3. Submit Song"
PAYLOAD=$(jq -n --arg url "$YT_URL" '{"url": $url, "speed": 1.0}')
SUBMIT=$(api_post "/songs" "$PAYLOAD") || fail "POST /songs failed"

SONG_ID=$(echo "$SUBMIT" | jq -r '.body.id')
SUBMIT_STATUS=$(echo "$SUBMIT" | jq -r '.body.status')
HTTP_CODE=$(echo "$SUBMIT" | jq -r '.status_code')

[[ "$HTTP_CODE" == "202" ]] || fail "Expected 202, got $HTTP_CODE"
[[ "$SUBMIT_STATUS" == "pending" ]] || fail "Expected status=pending, got $SUBMIT_STATUS"
[[ -n "$SONG_ID" && "$SONG_ID" != "null" ]] || fail "No song ID returned"

pass "POST /songs → 202 accepted, id=$SONG_ID"

# ── 4. GET song detail ────────────────────────────────────────────────────────
section "4. Song Detail"
DETAIL=$(api_get "/songs/$SONG_ID") || fail "GET /songs/$SONG_ID failed"
DETAIL_ID=$(echo "$DETAIL" | jq -r '.body.id')
[[ "$DETAIL_ID" == "$SONG_ID" ]] || fail "ID mismatch: expected $SONG_ID, got $DETAIL_ID"
pass "GET /songs/$SONG_ID → found"

# ── 5. Poll for done ──────────────────────────────────────────────────────────
section "5. Poll Until Done (timeout: ${POLL_TIMEOUT}s)"
ELAPSED=0
FINAL_STATUS=""

while [[ $ELAPSED -lt $POLL_TIMEOUT ]]; do
    POLL=$(api_get "/songs/$SONG_ID") || fail "Polling failed at ${ELAPSED}s"
    FINAL_STATUS=$(echo "$POLL" | jq -r '.body.status')

    case "$FINAL_STATUS" in
        done)
            TITLE=$(echo "$POLL" | jq -r '.body.title // "unknown"')
            DURATION=$(echo "$POLL" | jq -r '.body.duration // "?"')
            CHANNEL=$(echo "$POLL" | jq -r '.body.channel // "?"')
            pass "status=done after ${ELAPSED}s"
            info "  title:    $TITLE"
            info "  duration: ${DURATION}s"
            info "  channel:  $CHANNEL"
            break
            ;;
        failed)
            fail "Song processing failed after ${ELAPSED}s"
            ;;
        pending|processing)
            echo -ne "  ${YELLOW}status=${FINAL_STATUS} (${ELAPSED}s elapsed)...${NC}\r"
            sleep $POLL_INTERVAL
            ELAPSED=$((ELAPSED + POLL_INTERVAL))
            ;;
        *)
            fail "Unexpected status: $FINAL_STATUS"
            ;;
    esac
done

[[ "$FINAL_STATUS" == "done" ]] || fail "Timed out after ${POLL_TIMEOUT}s — final status: $FINAL_STATUS"

# ── 6. Stream audio ───────────────────────────────────────────────────────────
section "6. Stream Audio"
TMP_FILE=$(mktemp /tmp/melo_smoke_XXXXXX.mp3)
trap 'rm -f "$TMP_FILE"' EXIT

HTTP_STATUS=$(curl -sf --max-time 30 \
    -o "$TMP_FILE" \
    -w "%{http_code}" \
    "${API}/songs/${SONG_ID}/stream") || fail "GET /songs/$SONG_ID/stream failed"

[[ "$HTTP_STATUS" == "200" ]] || fail "Stream returned HTTP $HTTP_STATUS"

FILE_SIZE=$(wc -c < "$TMP_FILE")
[[ $FILE_SIZE -gt 1024 ]] || fail "Stream output suspiciously small: ${FILE_SIZE} bytes"

pass "GET /songs/$SONG_ID/stream → 200, ${FILE_SIZE} bytes"

# ── 7. Validation — bad URL ───────────────────────────────────────────────────
section "7. Validation (bad URL)"
BAD=$(curl -s --max-time 10 -X POST \
    -H "Content-Type: application/json" \
    -d '{"url": "https://vimeo.com/123456"}' \
    "${API}/songs")
BAD_CODE=$(echo "$BAD" | jq -r '.status_code // 200')
[[ "$BAD_CODE" == "422" ]] || fail "Expected 422 for invalid URL, got $BAD_CODE"
pass "POST /songs (bad URL) → 422"

# ── 8. Validation — bad speed ─────────────────────────────────────────────────
section "8. Validation (bad speed)"
BAD2=$(curl -s --max-time 10 -X POST \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$YT_URL\", \"speed\": 99.0}" \
    "${API}/songs")
BAD2_CODE=$(echo "$BAD2" | jq -r '.status_code // 200')
[[ "$BAD2_CODE" == "422" ]] || fail "Expected 422 for invalid speed, got $BAD2_CODE"
pass "POST /songs (bad speed) → 422"

# ── 9. 404 for unknown ID ─────────────────────────────────────────────────────
section "9. Not Found"
FAKE_ID="00000000-0000-0000-0000-000000000000"
NOT_FOUND=$(curl -s --max-time 10 "${API}/songs/${FAKE_ID}")
NF_CODE=$(echo "$NOT_FOUND" | jq -r '.status_code // 200')
[[ "$NF_CODE" == "404" ]] || fail "Expected 404 for unknown ID, got $NF_CODE"
pass "GET /songs/$FAKE_ID → 404"

# ── 10. List songs (post-submit count) ───────────────────────────────────────
section "10. List Songs (post-submit)"
LIST2=$(api_get "/songs") || fail "GET /songs failed"
FINAL_COUNT=$(echo "$LIST2" | jq -r '.body.count')
[[ $FINAL_COUNT -gt $INITIAL_COUNT ]] || fail "Song count did not increase (was $INITIAL_COUNT, now $FINAL_COUNT)"
pass "GET /songs → $FINAL_COUNT songs (+$((FINAL_COUNT - INITIAL_COUNT)))"

# ── Summary ───────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}══════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ All smoke tests passed!${NC}"
echo -e "${GREEN}══════════════════════════════════${NC}\n"
