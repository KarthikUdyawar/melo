# Melo — Handoff Document

**Date:** 2026-05-31
**Repo:** `KarthikUdyawar/melo`
**Active branch:** `feature/ui-scaffold` (seeking fix in progress, not yet committed)
**Active skills:** `/caveman ultra`, `/clean-code`, `/tdd`

---

## Session Summary

1. **`make tree`** added to Makefile.
2. **UI-0 confirmed complete** — `feature/ui-scaffold` → `develop` ready to merge.
3. **Audio playback bug fixed** — `handleGlobalClick` early `return` blocked card clicks. Fixed by moving card/playlist checks above action guard.
4. **Audio seeking root cause diagnosed** — stream endpoint returns `200 OK` with no `Accept-Ranges`, browser treats stream as non-seekable.
5. **`songs.py` rewritten** for range support — see below.
6. **Seeking still unverified** — session ended before final confirmation.

---

## Seeking Fix — Status

Latest `songs.py` at `/mnt/user-data/outputs/songs.py`:

- **No trim/speed:** `httpx.get(internal_presigned_url, headers={"Range": ...})` → proxied `Response` with `Accept-Ranges: bytes`. Uses `minio:9000` (internal) — API container can reach it, signature valid.
- **Trim/speed:** `FileResponse(final_path, background=BackgroundTask(_cleanup))` — Starlette handles `206` natively.
- `StreamingResponse` removed from both paths.
- `stream_song` now takes `request: Request` for Range header forwarding.

Apply:
```bash
cp /mnt/user-data/outputs/songs.py app/api/songs.py
# auto-reloads via uvicorn --reload
```

Verify:
```bash
curl -H "Range: bytes=0-1023" -I http://localhost:8000/songs/<done-id>/stream
# Must return: HTTP/1.1 206 Partial Content + Accept-Ranges: bytes
```

If 502: `docker compose logs api --tail=30` for httpx traceback.

---

## Sprint 4 Status

| Ticket | Status | Notes |
|--------|--------|-------|
| UI-0 — Scaffold | ✅ done | Merge to develop |
| UI-1 — Library | 🟡 partial | Missing: Retry on failed cards |
| UI-2 — Add Song Modal | 🟡 partial | Missing: loading spinner |
| UI-3 — Player Bar | 🟡 partial | Play/pause works. **Seeking broken (P0)** |
| UI-4 — Favorites | ⬜ todo | |
| UI-5 — Playlists | ⬜ todo | |
| UI-6 — Polish | ⬜ todo | |

---

## Files Changed This Session (uncommitted)

| File | Where | Notes |
|------|-------|-------|
| `app/api/songs.py` | `/mnt/user-data/outputs/songs.py` | Copy + verify seeking |
| `ui/player.js` | `/mnt/user-data/outputs/player.js` | Improved scrubber — apply after seeking confirmed |
| `ui/app.js` | In repo | Card click fix applied; debug `console.log` lines present — remove before merge |

---

## Known Bugs

- "Load more" shows with 1 song (bookmark null check too late) — UI-6 scope
- Active card highlight only updates visible cards on play — UI-6 scope
- `share-modal.js` console error — browser extension, not Melo

## Constraints
- Caveman ultra active
- Clean code — SRP, ≤20 line functions
- No build tooling, no TypeScript, no frontend tests
- Design tokens only — no raw hex in CSS
- Python changes hot-reload; UI changes need `docker compose build ui && docker compose up -d ui`
