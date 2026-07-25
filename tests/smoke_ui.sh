#!/usr/bin/env bash
# tests/smoke_ui.sh — UI smoke tests (curl only, no browser)
# Requires: docker compose up (ui on :3000, api on :8000)

set -uo pipefail  # -e removed: test failures must not abort script

UI_BASE="${UI_BASE:-http://localhost:3000}"
API_BASE="${API_BASE:-http://localhost:8000}"

PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS${NC}  $1"; ((PASS++)) || true; }
fail() { echo -e "${RED}❌ FAIL${NC}  $1"; ((FAIL++)) || true; }

check_status() {
  local label="$1" url="$2" expected="$3"
  local actual
  actual=$(curl -s -o /dev/null -w "%{http_code}" "$url")
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

# ── nginx proxy → api ─────────────────────────────────────────────────────────

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
