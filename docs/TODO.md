# Melo — TODO

> Single source for open work. See `PRD.md` for full Sprint 6 spec, `ROADMAP.md` for sprint history.

---

## Sprint 6 — Frontend Polish

### Blocking — resolved

- [x] **Waveform placement**: expandable "now playing" panel (new UI surface — FE-3 scope up from inline default)
- [x] **Nav pattern**: bottom tab bar (phone) + icon rail 56px, no drawer (tablet) — Spotify-style

### FE-0 — Responsive Layout

- [ ] Breakpoints: desktop >=1280px (unchanged), tablet 768-1279px, phone <=767px
- [ ] Tablet: sidebar -> icon rail (56px), no drawer, no hamburger needed
- [ ] Phone: sidebar -> bottom tab bar (Library/Favorites/Playlists)
- [ ] Phone: song card stacks title under thumbnail
- [ ] Phone: player bar compacts -- thumb + title + play/pause + scrubber only, hide time labels + prev/next
- [ ] Modal: full-screen below 768px, no radius/backdrop margin
- [ ] CSS-only breakpoint switching -- no JS layout logic beyond drawer/tab-bar toggle state

### FE-1 — Player Features (depends: FE-0)

- [ ] Volume: slider in player bar, persist `localStorage['melo:volume']`, default 1.0
- [ ] Volume: click icon to mute/unmute, remembers pre-mute level
- [ ] Loop: off/one/all, persist `localStorage['melo:loop']`, default off, icon-button 3-state
- [ ] Shuffle: session-only (not persisted), Fisher-Yates reshuffle, keeps current song in place on toggle
- [ ] Queue: set from clicked song's page list (Library/Favorites/Playlist Detail) + clicked index
- [ ] `audio.onended`: loop-one replays, else advance queue (wrap if loop-all), stop + keep bar visible if loop-off at queue end
- [ ] Prev/Next buttons operate on queue

### FE-2 — Drag-Reorder Playlists (depends: FE-0)

- [ ] Backend: `PATCH /playlists/{id}/songs/{song_id}` body `{ "position": int }`
- [ ] Shift-down logic between old/new position (not a two-item swap)
- [ ] Retry on `IntegrityError` vs `uq_playlist_position`, reusing existing pattern from `add_song_to_playlist`
- [ ] Response: `200` + updated playlist detail / `404` / `422` out-of-range / `409` conflict after retries
- [ ] Frontend: native HTML5 DnD (`draggable`, `dragstart`/`dragover`/`drop`) on Playlist Detail rows, via existing event-delegation listener
- [ ] Frontend: optimistic reorder, re-fetch on failure to resync

### FE-3 — Waveform Display (depends: FE-0, FE-1)

- [ ] New "Now Playing" panel — full view, opens from player bar (tap thumb/title), new UI surface
- [ ] Panel: large thumbnail, title, channel, waveform canvas, transport controls (mirrors player bar), close button
- [ ] Fetch stream URL as `ArrayBuffer` on first play (separate from `<audio>` playback)
- [ ] `AudioContext.decodeAudioData()` -> downsample to ~200 peak buckets
- [ ] Render peaks to `<canvas>` inside Now Playing panel
- [ ] Cache peaks in-memory `Map<songId, peaks>` per session, no persistence
- [ ] Out of scope this sprint: click-to-seek on waveform

### FE-4 — Accessibility Audit (depends: FE-0-FE-3)

- [ ] Dropdown: close on `Escape`, same listener as modal-close
- [ ] Modal: manual focus trap (query focusables, wrap `Tab`/`Shift+Tab`)
- [ ] `#toast-root`: `aria-live="polite"`
- [ ] Status pill: `aria-label` matching visible text
- [ ] Manual tab-order pass across all pages incl. new FE-0-FE-3 markup

### FE-5 — UX Bug Fixes (ongoing, audit-driven)

- [ ] Log bugs found during FE-0-FE-4 here as they surface -- no fixed list at sprint start

### FE-6 — Tests (depends: FE-2)

- [ ] Unit: reorder correctly shifts positions (not a swap)
- [ ] Unit: reorder retries on `IntegrityError`
- [ ] Integration: `422` on out-of-range position
- [ ] Integration: `404` on missing playlist/song/membership
- [ ] Integration: full reorder reflected in `GET /playlists/{id}`
- [ ] Manual smoke additions to `smoke-ui.sh`: responsive breakpoints, player controls (volume/shuffle/loop/autoplay), drag-drop, waveform render, focus trap, dropdown Escape-close
- [ ] Maintain >=80% backend coverage (currently 91%) -- FE-2 endpoint is the only backend surface this sprint

---

## Sprint 7+

Not scoped yet. Candidates already known but deferred:

- Waveform click-to-seek
- Bulk/multi-select playlist reorder
- Multi-user auth, Alembic -- still explicitly out of scope, not just deferred
