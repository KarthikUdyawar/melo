#!/usr/bin/env bash
# tests/smoke_ui.sh — UI smoke tests (curl only, no browser)
# Requires: docker compose up (ui on :3000, api on :8000), jq installed

set -uo pipefail  # -e removed: test failures must not abort script

UI_BASE="${UI_BASE:-http://localhost:3000}"
API_BASE="${API_BASE:-http://localhost:8000}"
NIL_UUID="00000000-0000-0000-0000-000000000000"

PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS${NC}  $1"; ((PASS++)) || true; }
fail() { echo -e "${RED}❌ FAIL${NC}  $1"; ((FAIL++)) || true; }

check_status() {
  local label="$1" url="$2" expected="$3" method="${4:-GET}" body="${5:-}"
  local actual
  if [[ -n "$body" ]]; then
    actual=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" -d "$body" "$url")
  else
    actual=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$url")
  fi
  if [[ "$actual" == "$expected" ]]; then
    pass "$label (HTTP $actual)"
  else
    fail "$label — expected $expected, got $actual  [$url]"
  fi
}

check_contains() {
  local label="$1" url="$2" pattern="$3"
  local body
  body=$(curl -sf "$url" 2>/dev/null || true)
  if echo "$body" | grep -q "$pattern" 2>/dev/null; then
    pass "$label"
  else
    fail "$label — pattern '$pattern' not found in response"
  fi
}

check_header() {
  local label="$1" url="$2" pattern="$3"
  local headers
  headers=$(curl -sI "$url" 2>/dev/null | tr -d '\r' || true)
  if echo "$headers" | grep -qi "$pattern" 2>/dev/null; then
    pass "$label"
  else
    fail "$label — header pattern '$pattern' not found"
  fi
}

check_header_get() {
  local label="$1" url="$2" pattern="$3"
  local headers
  headers=$(curl -s -D - -o /dev/null "$url" 2>/dev/null | tr -d '\r' || true)
  if echo "$headers" | grep -qi "$pattern" 2>/dev/null; then
    pass "$label"
  else
    fail "$label — header pattern '$pattern' not found"
  fi
}

has_jq() { command -v jq >/dev/null 2>&1; }

echo ""
echo "🎵 Melo UI Smoke Tests"
echo "   UI:  $UI_BASE"
echo "   API: $API_BASE"
echo ""

# ── nginx serving ─────────────────────────────────────────────────────────────

check_status   "UI root serves index.html"              "$UI_BASE/"              "200"
check_contains "index.html contains app shell"          "$UI_BASE/"              "class=\"sidebar"
check_contains "index.html loads style.css"             "$UI_BASE/"              "style.css"
check_contains "index.html loads app.js module"         "$UI_BASE/"              "type=\"module\""
check_status   "style.css served"                       "$UI_BASE/style.css"     "200"
check_status   "api.js served"                          "$UI_BASE/api.js"        "200"
check_status   "player.js served"                       "$UI_BASE/player.js"     "200"
check_status   "components.js served"                   "$UI_BASE/components.js" "200"
check_status   "app.js served"                          "$UI_BASE/app.js"        "200"

# ── SPA fallback ──────────────────────────────────────────────────────────────

check_status   "Unknown path → SPA fallback (not 404)"  "$UI_BASE/nonexistent"   "200"
check_contains "SPA fallback returns index.html"        "$UI_BASE/some/deep/path" "class=\"sidebar"

# ── nginx proxy → api (basic reachability) ────────────────────────────────────

check_status   "Proxy /api/health → API"                "$UI_BASE/api/health"    "200"
check_contains "Proxy returns valid envelope"           "$UI_BASE/api/health"    "status_code"
check_contains "Health body shows ok"                  "$UI_BASE/api/health"    "\"ok\""
check_status   "Proxy GET /api/songs → API"             "$UI_BASE/api/songs"     "200"
check_contains "Songs response has records key"        "$UI_BASE/api/songs"     "records"
check_status   "Proxy GET /api/playlists → API"         "$UI_BASE/api/playlists" "200"
check_status   "Proxy GET /api/favorites → API"         "$UI_BASE/api/favorites" "200"

# ── content-type headers ──────────────────────────────────────────────────────

check_header   "style.css served as text/css"           "$UI_BASE/style.css"     "text/css"
check_header   "app.js served as javascript"            "$UI_BASE/app.js"        "javascript"

# ── proxy is forwarding (server header present) ───────────────────────────────

check_header   "Proxy response has server header"       "$UI_BASE/api/health"    "server:"

# ── trace correlation (Sprint 5, previously unverified via UI proxy) ──────────

check_header   "Proxy response carries X-Trace-Id"      "$UI_BASE/api/health"    "x-trace-id:"

# ── songs: preview + not-found paths (previously unverified via UI proxy) ─────

check_status   "Preview: invalid URL → 422" \
  "$UI_BASE/api/songs/preview" "422" "POST" '{"url":"not-a-youtube-url"}'

check_status   "GET unknown song → 404" \
  "$UI_BASE/api/songs/$NIL_UUID" "404"

check_status   "Stream unknown song → 404" \
  "$UI_BASE/api/songs/$NIL_UUID/stream" "404"

check_status   "DELETE unknown song → 404" \
  "$UI_BASE/api/songs/$NIL_UUID" "404" "DELETE"

# ── metrics (proxied but unenveloped — previously unverified via UI proxy) ────

check_status   "Proxy GET /api/metrics → API"           "$UI_BASE/api/metrics"   "200"
check_header_get "Metrics served as text/plain"         "$UI_BASE/api/metrics"   "text/plain"

# ── favorites: idempotency + not-found (previously unverified via UI proxy) ───

check_status   "Favorite unknown song → 404" \
  "$UI_BASE/api/favorites/$NIL_UUID" "404" "POST"

check_status   "Unfavorite unknown song → 404" \
  "$UI_BASE/api/favorites/$NIL_UUID" "404" "DELETE"

# ── playlists: full CRUD lifecycle (previously unverified via UI proxy) ───────

if has_jq; then
  playlist_id=""
  create_resp=$(curl -s -X POST -H "Content-Type: application/json" \
    -d '{"name":"__smoke_test_playlist__"}' "$UI_BASE/api/playlists")
  playlist_id=$(echo "$create_resp" | jq -r '.body.id // empty' 2>/dev/null)

  if [[ -n "$playlist_id" ]]; then
    pass "Create playlist via proxy"

    check_status "GET created playlist → 200" \
      "$UI_BASE/api/playlists/$playlist_id" "200"

    check_status "Add unknown song to playlist → 404" \
      "$UI_BASE/api/playlists/$playlist_id/songs/$NIL_UUID" "404" "POST"

    check_status "Remove unknown song from playlist → 404" \
      "$UI_BASE/api/playlists/$playlist_id/songs/$NIL_UUID" "404" "DELETE"

    # FE-2 reorder — 422 out-of-range on an empty playlist (song_count=0, any position invalid)
    check_status "Reorder on unknown membership → 404" \
      "$UI_BASE/api/playlists/$playlist_id/songs/$NIL_UUID" "404" "PATCH" '{"position":0}'

    check_status "Cleanup: delete smoke test playlist → 204" \
      "$UI_BASE/api/playlists/$playlist_id" "204" "DELETE"
  else
    fail "Create playlist via proxy — could not parse id from response"
  fi
else
  echo "⚠️  jq not found — skipping playlist CRUD lifecycle checks (create/get/cleanup)"
fi

check_status   "Reorder unknown playlist → 404" \
  "$UI_BASE/api/playlists/$NIL_UUID/songs/$NIL_UUID" "404" "PATCH" '{"position":0}'

check_status   "DELETE unknown playlist → 404" \
  "$UI_BASE/api/playlists/$NIL_UUID" "404" "DELETE"

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
echo "────────────────────────────────"
TOTAL=$((PASS + FAIL))
echo "Results: $PASS/$TOTAL passed"
if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}$FAIL test(s) failed${NC}"
  exit 1
else
  echo -e "${GREEN}All UI smoke tests passed ✅${NC}"
fi
echo ""

# ── MANUAL BROWSER CHECKS (not automatable via curl) ─────────────────────────
# Run these by hand against $UI_BASE in an actual browser:
#   [ ] Drag a song to a new position in a 3+ song playlist -> order updates, persists on refresh
#   [ ] Drag a song onto itself -> no-op, no network call fires
#   [ ] Kill API mid-drag (stop container) -> error toast shows, list resyncs to server state
#   [ ] Responsive breakpoints: 1280px/768px/480px tiers render correctly
#   [ ] Player: volume slider + mute/unmute remembers level
#   [ ] Player: loop off/one/all cycles correctly, shuffle keeps current song in place
#   [ ] Waveform renders in Now Playing panel, cached per session
#   [ ] Modal focus trap: Tab/Shift+Tab wraps inside open modal
#   [ ] Dropdown closes on Escape
