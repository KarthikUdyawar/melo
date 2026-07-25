# Melo — Sprint 6: Frontend Polish

**Owner:** Karthik | **Repo:** `melo` | **Sprint:** 6 | **Timeline:** no fixed deadline (solo)
**Reverses:** Sprint 4 decision "no responsive/mobile layout" (`DECISIONS.md`) — mobile support now in scope.

---

## Problem

Melo's UI is desktop-only (1280px min), has no volume/shuffle/loop/autoplay, no playlist reordering, no waveform, and hasn't had an accessibility pass since Sprint 4. Solo-use is fine on a desktop, but the app is unusable on a phone and the player is missing controls any music app is expected to have.

---

## Goal

> *Melo works and feels good on a phone, and the player behaves like a real music player.*

---

## Scope

### ✅ In

| Ticket | Feature                                                            |
| ------ | ------------------------------------------------------------------ |
| FE-0   | Responsive layout — desktop/tablet/phone breakpoints               |
| FE-1   | Player features — volume, shuffle, loop, autoplay-next             |
| FE-2   | Drag-reorder playlists (native HTML5 DnD + backend position PATCH) |
| FE-3   | Waveform display (client-side, no stored variant)                  |
| FE-4   | Accessibility audit — keyboard, focus, aria                        |
| FE-5   | UX bug fixes — audit-driven, logged in `TODO.md` as found          |
| FE-6   | Tests — backend TDD for new endpoint; manual smoke for frontend    |

### ❌ Out

- Waveform *seeking* (click-to-scrub on waveform) — display only this sprint, seek is a candidate for Sprint 7
- Multi-user auth, Alembic — still explicitly out of scope per prior sprints
- Bulk/multi-select drag reorder — one song moved at a time

---

## FE-0 — Responsive Layout

**Breakpoints** (mobile-first CSS, existing desktop styles become the `min-width: 1280px` tier):

| Tier    | Width      | Layout change                                                                                                                                                                                             |
| ------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Desktop | ≥ 1280px   | Current: fixed 220px sidebar + main + player bar (unchanged)                                                                                                                                              |
| Tablet  | 768–1279px | Sidebar collapses to icon-only rail (56px), always visible, no drawer/hamburger — Spotify-style                                                                                                           |
| Phone   | ≤ 767px    | Sidebar becomes a bottom tab bar (Library/Favorites/Playlists); song card stacks title under thumbnail; player bar compacts (thumb + title + play/pause + scrubber only, hides time labels and prev/next) |

**Modal:** full-screen (no border radius, no backdrop margin) below 768px — matches native app-sheet feel rather than a floating card.

**Grid:** replace fixed `grid-template-columns: 220px 1fr` with a CSS variable swapped per breakpoint via media query, so `app.js` doesn't need JS-driven layout logic — pure CSS.

**No new JS framework** — hamburger/drawer toggle is a small state flag + class toggle in `app.js`, consistent with existing event-delegation pattern.

---

## FE-1 — Player Features

New player state (module-scope in `player.js`, alongside the existing `<audio>` element):

```
volume     0.0–1.0, persisted to localStorage['melo:volume'], default 1.0
loopMode   'off' | 'one' | 'all', persisted to localStorage['melo:loop'], default 'off'
shuffle    boolean, session-only (not persisted — tied to the current queue)
queue      ordered list of song ids the player is currently traversing + currentIndex
```

**Queue semantics:**
- Loading a song from any page (Library/Favorites/Playlist Detail) sets `queue` = that page's current visible song list (in list order), `currentIndex` = clicked song's position.
- Shuffle on: `queue` reshuffled (Fisher–Yates) but `currentIndex` repositioned to keep the currently-playing song in place — toggling shuffle mid-playback doesn't skip the current song.
- `audio.onended`:
  - `loopMode === 'one'` → replay same song
  - else advance `currentIndex` (wrapping if `loopMode === 'all'`)
  - `loopMode === 'off'` and at end of queue → stop, player bar stays visible on last song (not hidden)
- Prev/Next buttons operate on the same queue, independent of autoplay.

**UI additions to Player Bar** (see FE-0 for phone-tier hides): volume slider (icon + `<input type="range">`, click icon to mute/unmute — remembers pre-mute volume), shuffle icon-button (toggled state = accent color), loop icon-button (three visual states: off / one / all — reuses existing icon-button pattern from `components.js`).

---

## FE-2 — Drag-Reorder Playlists

### API: `PATCH /playlists/{id}/songs/{song_id}`

**Request body:**
```json
{ "position": 2 }
```

**Behavior:** moves the song to the given 0-indexed position within that playlist; every other song's `position` shifts accordingly (shift-down between old and new position). Reuses the existing retry-on-`IntegrityError` pattern from `add_song_to_playlist` against `uq_playlist_position`.

| Status | Meaning                                            |
| ------ | -------------------------------------------------- |
| `200`  | Reordered — returns updated playlist detail        |
| `404`  | Playlist, song, or membership not found            |
| `422`  | `position` out of range (`< 0` or `>= song_count`) |
| `409`  | Position conflict after retries                    |

No model changes — reuses `PlaylistSong.position`.

### Frontend

Native HTML5 drag-and-drop on Playlist Detail rows (`draggable="true"`, `dragstart`/`dragover`/`drop` handlers via the existing event-delegation listener in `app.js` — no new library, consistent with Sprint 4's no-framework decision). On `drop`: optimistic reorder in the DOM, `PATCH` call, re-fetch on failure to resync.

---

## FE-3 — Waveform Display

**Client-side only** — no backend change, no stored variant (consistent with the "trim/speed at stream time, one source file" philosophy from `PIPELINE.md`/`DECISIONS.md`).

**New surface: Now Playing panel.** Waveform lives in a new full view, not the 72px player bar (too cramped). Tapping the thumbnail/title in the player bar opens it; a close button (or `Esc`) returns to the previous page. Panel content: large thumbnail, title, channel, waveform canvas, transport controls (play/pause, prev/next, scrubber, volume, shuffle, loop — mirrors player bar state, doesn't duplicate it).

**Flow:**
1. On first play of a song, `player.js` fetches the stream URL as an `ArrayBuffer` (separate from the `<audio>` element's own streaming playback).
2. `AudioContext.decodeAudioData()` → extract peak amplitudes (downsampled to ~200 buckets).
3. Render to a `<canvas>` inside the Now Playing panel.
4. Cache peaks in an in-memory `Map<songId, peaks>` for the session — avoids re-fetching/re-decoding on repeat plays; cache is cleared on page reload (no persistence).

**Not in scope:** click-to-seek on the waveform (visual only this sprint).

---

## FE-4 — Accessibility Audit

| Gap                                                                        | Fix                                                                                     |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Song-card dropdown only closes on outside click (`USER-FLOW.md` §Keyboard) | Add `Escape` handling to close dropdown, same listener that already closes modals       |
| Modals have no focus trap                                                  | Minimal manual focus trap: query focusable elements in `.modal`, wrap `Tab`/`Shift+Tab` |
| Toast/status-pill changes not announced                                    | Add `aria-live="polite"` to `#toast-root`; status pill gets `aria-label` matching text  |
| Tab order not verified                                                     | Manual pass — no automated a11y test tooling introduced this sprint                     |

Existing principles (`DESIGN.md`: focus-visible rings, aria-label on icon buttons, color-not-sole-indicator) already in place — this ticket closes the gaps, not a rewrite.

---

## FE-5 — UX Bug Fixes

Audit-driven. No fixed list at sprint start — bugs found during FE-0…FE-4 work (or reported separately) get logged in `TODO.md` under a Sprint 6 section as found, then fixed in this ticket. `TODO.md` currently empty; this sprint is what fills it.

---

## FE-6 — Tests

| Behavior                                                             | Type        |
| -------------------------------------------------------------------- | ----------- |
| `PATCH /playlists/{id}/songs/{song_id}` reorders positions correctly | Unit        |
| Reorder shifts intermediate songs' positions, doesn't just swap two  | Unit        |
| Reorder retries on `IntegrityError` against `uq_playlist_position`   | Unit        |
| Reorder returns `422` for out-of-range position                      | Integration |
| Reorder returns `404` for missing playlist/song/membership           | Integration |
| Full reorder → `GET /playlists/{id}` reflects new order              | Integration |

Frontend (player queue/shuffle/loop, waveform peaks, drag-drop, responsive breakpoints, focus trap): **manual smoke only** — Sprint 4's "no frontend tests, no framework = no component test surface" decision still holds. `smoke-ui.sh` gets new manual-check entries, not automated assertions.

Coverage target: maintain ≥ 80% on backend (currently 91%) — FE-2's new endpoint is the only backend surface this sprint touches.

---

## Ticket Breakdown & Order

| Ticket | Depends on | Notes                                                           |
| ------ | ---------- | --------------------------------------------------------------- |
| FE-0   | —          | Foundation — do first, everything else builds on the new layout |
| FE-1   | FE-0       | Player bar changes assume responsive shell exists               |
| FE-2   | FE-0       | Playlist Detail page changes assume responsive shell            |
| FE-3   | FE-0, FE-1 | Waveform lives in the player bar FE-1 builds out                |
| FE-4   | FE-0–FE-3  | Audits the new markup, not just the old                         |
| FE-5   | ongoing    | Runs alongside FE-0–FE-4, not a discrete phase                  |
| FE-6   | FE-2       | Backend tests as soon as FE-2's endpoint exists                 |

---

## Open Questions — resolved

- Waveform placement → expandable "now playing" panel (Karthik's call). FE-3 scope increased accordingly (new panel UI, not just a canvas drop-in).
- Nav pattern → bottom tabs (phone) + icon rail, no drawer (tablet), Spotify-style (Karthik's call).

---

## Decision Log

| Decision                                                         | Reason                                                                                              |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Mobile support added, overturning Sprint 4's "desktop-only" call | Karthik's call this sprint — personal use now includes phone                                        |
| Breakpoints 1280 / 768 / 480(-ish, "phone" tier ≤767)            | Standard tablet/phone split; desktop tier unchanged from existing CSS                               |
| Sidebar → bottom tab bar on phone, icon rail/drawer on tablet    | Matches common mobile music-app patterns; avoids a hamburger-only phone nav                         |
| Reorder API: single-song `PATCH`, not a bulk ordered-list `POST` | Simpler diff against existing `position`-shift logic; Karthik's call, accepts N calls on multi-move |
| Queue reshuffle keeps current song in place                      | Toggling shuffle mid-playback shouldn't interrupt what's currently playing                          |
| Waveform computed client-side, cached in-memory only             | No new stored variant (matches existing trim/speed-at-stream philosophy); avoids disk/MinIO cost    |
| Loop 'off' at end of queue stops but keeps player bar visible    | Matches Sprint 4's existing choice to not auto-hide the player bar except on song deletion          |
| FE-5 has no fixed scope at sprint start                          | Karthik chose audit-as-we-go over a pre-supplied bug list                                           |
| No automated frontend tests introduced                           | Consistent with Sprint 4 decision — still no component framework/test surface                       |
| Tablet nav = icon rail (56px), no drawer/hamburger               | Spotify-style; Karthik's call, simpler than a toggled drawer                                        |
| Waveform → new expandable Now Playing panel, not inline in bar   | Karthik's call; 72px bar too cramped for a useful waveform — FE-3 scope grows to include the panel  |
