# Melo — TODO

> Single source for open work. See `PRD.md` for full Sprint 6 spec, `ROADMAP.md` for sprint history.

---

## Sprint 6 — Frontend Polish

### Blocking — resolved

- [x] **Waveform placement**: expandable "now playing" panel (new UI surface — FE-3 scope up from inline default)
- [x] **Nav pattern**: bottom tab bar (phone) + icon rail 56px, no drawer (tablet) — Spotify-style

### FE-0 — Responsive Layout ✅ done

- [x] Breakpoints: desktop >=1280px (unchanged), tablet 768-1279px, phone <=767px
- [x] Tablet: sidebar -> icon rail (56px), no drawer, no hamburger needed
- [x] Phone: sidebar -> bottom tab bar (Library/Favorites/Playlists)
- [x] Phone: song card stacks title under thumbnail
- [x] Phone: player bar compacts -- thumb + title + play/pause + scrubber only, hide time labels + prev/next
- [x] Modal: full-screen below 768px, no radius/backdrop margin
- [x] CSS-only breakpoint switching -- no JS layout logic beyond drawer/tab-bar toggle state
- [x] Phone-only: Add Song FAB added (sidebar's add button is hidden on phone with no sidebar) -- not in original PRD wording, needed since nav tabs don't include Add

### FE-1 — Player Features ✅ done (depends: FE-0)

- [x] Volume: slider in player bar, persist `localStorage['melo:volume']`, default 1.0
- [x] Volume: click icon to mute/unmute, remembers pre-mute level
- [x] Loop: off/one/all, persist `localStorage['melo:loop']`, default off, icon-button 3-state
- [x] Shuffle: session-only (not persisted), Fisher-Yates reshuffle, keeps current song in place on toggle
- [x] Queue: set from clicked song's page list (Library/Favorites/Playlist Detail) + clicked index
- [x] `audio.onended`: loop-one replays, else advance queue (wrap if loop-all), stop + keep bar visible if loop-off at queue end
- [x] Prev/Next buttons operate on queue, skip non-`done` entries

### FE-2 — Drag-Reorder Playlists ✅ done (depends: FE-0)

- [x] Backend: `PATCH /playlists/{id}/songs/{song_id}` body `{ "position": int }`
- [x] Shift-down logic between old/new position (not a two-item swap)
- [x] ~~Retry on `IntegrityError` vs `uq_playlist_position`~~ — N/A, see DECISIONS.md (sentinel approach has no retry loop)
- [x] Response: `200` + updated playlist detail / `404` / `422` out-of-range — 409 dropped, see DECISIONS.md
- [x] Frontend: native HTML5 DnD (`draggable`, `dragstart`/`dragover`/`drop`) on Playlist Detail rows, via existing event-delegation listener
- [x] Frontend: optimistic reorder, re-fetch on failure to resync
- [x] Manually confirmed working in browser by Karthik

### FE-3 — Waveform Display ✅ done (depends: FE-0, FE-1)

- [x] New "Now Playing" panel — full view, opens from player bar (tap thumb/title), new UI surface
- [x] Panel: large thumbnail, title, channel, waveform canvas, transport controls (mirrors player bar), close button
- [x] Fetch stream URL as `ArrayBuffer` on first play (separate from `<audio>` playback)
- [x] `AudioContext.decodeAudioData()` -> downsample to ~200 peak buckets
- [x] Render peaks to `<canvas>` inside Now Playing panel
- [x] Cache peaks in-memory `Map<songId, peaks>` per session, no persistence — lives in `player.js` module scope, not `app.js`
- [ ] Out of scope this sprint: click-to-seek on waveform
- [x] Panel scrubber (separate control from the waveform) supports click-to-seek — bug found in manual testing, was shipped `disabled`; see DECISIONS.md
- [x] Loop-mode badge ("1" in loop-one state) renders correctly in both player bar and panel — bug found in manual testing, was ID-scoped CSS; see DECISIONS.md
- [x] Panel state (play/pause, scrubber, volume, shuffle, loop, song swap on next/prev) mirrors player bar live via `player.js`'s new `subscribe()` pub-sub
- [x] Manually confirmed working in browser by Karthik, 2 bugs found + fixed (scrubber dead, loop badge missing)

### FE-4 — Accessibility Audit (depends: FE-0-FE-3)

- [ ] Dropdown: close on `Escape`, same listener as modal-close
- [ ] Modal: manual focus trap (query focusables, wrap `Tab`/`Shift+Tab`)
- [ ] `#toast-root`: `aria-live="polite"`
- [ ] Status pill: `aria-label` matching visible text
- [ ] Manual tab-order pass across all pages incl. new FE-0-FE-3 markup

### FE-5 — UX Bug Fixes (ongoing, audit-driven)

- [ ] Log bugs found during FE-0-FE-4 here as they surface -- no fixed list at sprint start

Flagged during FE-0/FE-1 (not bugs, undocumented calls -- confirm or override):
- [ ] `prev()` restarts current song if >3s played, only jumps to previous track if <3s in -- standard player convention, not in original PRD spec. Confirm keep or remove.
- [ ] Song card "stacks title under thumbnail" on phone implemented as: thumb top (64px), title/meta/actions stacked below -- literal reading of PRD wording, not yet visually confirmed by Karthik on a device

Flagged during FE-2 (not bugs, undocumented calls -- confirm or override):
- [x] Drop-onto-row semantics implemented as "insert after target row" (splice at dropped-on index) -- not specified in PRD. **Resolved: keeping as-is** (Karthik confirmed working via manual test; no request to change). See DECISIONS.md.
- [ ] Song thumbnail inside dragged row is natively `draggable` in most browsers, so the drag-preview image shows just the thumbnail, not the full row -- cosmetic only, reorder still functions correctly. Low priority; fix requires `draggable="false"` on shared `.song-card__thumb` in `components.js` (touches Library/Favorites too). Confirm fix now or defer to Sprint 7.

### FE-6 — Tests (depends: FE-2) ✅ backend + smoke done

- [x] Unit: reorder correctly shifts positions (not a swap)
- [x] Unit: reorder retries on `IntegrityError` — N/A, see DECISIONS.md (sentinel approach has no retry loop)
- [x] Integration: `422` on out-of-range position
- [x] Integration: `404` on missing playlist/song/membership
- [x] Integration: full reorder reflected in `GET /playlists/{id}`
- [x] `smoke_test.sh` S17: reorder end-to-end (shift-not-swap, 422/404 paths, separate-GET reflection) — full suite 27/27 passing
- [x] `smoke_ui.sh`: proxy-layer contract checks for reorder (404 paths through nginx), plus expanded coverage for previously-untested proxied endpoints (preview validation, stream 404, metrics content-type, playlist CRUD lifecycle, trace header) — 38/38 passing
- [ ] Manual smoke checklist added to `smoke_ui.sh` (comment block, not automatable via curl): responsive breakpoints, player controls (volume/shuffle/loop/autoplay), drag-drop DOM behavior, waveform render, focus trap, dropdown Escape-close — still require an actual browser
- [x] Maintain >=80% backend coverage (currently 91%) -- FE-2 endpoint is the only backend surface this sprint

---

## Sprint 7+

Not scoped yet. Candidates already known but deferred:

- Waveform click-to-seek
- Bulk/multi-select playlist reorder
- Fix drag-preview showing only thumbnail (cosmetic, `draggable="false"` on `.song-card__thumb`) — deferred from FE-5, see flagged item above
- Multi-user auth, Alembic -- still explicitly out of scope, not just deferred
