# Melo — TODO

> Single source for open work. See `PRD.md` for full Sprint 6 spec, `ROADMAP.md` for sprint history.

---

## Sprint 7 — Frontend Rewrite (Next.js/TS/Tailwind)

- [x] Brainstorm/decisions locked: real routes, msw, self-signed HTTPS
- [ ] FE7-0 Scaffold
- [ ] FE7-1 Tailwind tokens
- [x] FE7-2 Port components — StatusPill, SongCard, SongCardMenu, PlaylistCard,
      ToastProvider/useToast, generic Modal shell, ConfirmDialog (moved here from
      its original FE7-2 PRD row — AddSongModal stays FE7-8's scope). Helpers:
      formatDuration, trapFocus (both TDD'd). 43/43 tests passing.
- [x] FE7-3 `lib/api.ts` + msw test setup — `types.ts` (Song/Playlist/Envelope/ApiError), `api.ts` (all endpoint wrappers, envelope unwrap ported from `apiFetch()`), `test/server.ts` + `test/handlers.ts` + `test/msw-polyfills.ts`, full test suite green
- [ ] FE7-4 `PlayerProvider`
- [ ] FE7-5 Real routes + `/playlists/[id]` client-resolved shell + nginx rewrite —
      **in progress, currently broken.** Library/Favorites/Playlists/PlaylistDetail
      pages + Nav (sidebar/tab-bar) written, wired to lib/api.ts and FE7-2 components.
      `pnpm build` fails: `/playlists/[id]/page.tsx` combines `"use client"` with
      `generateStaticParams()` — Next disallows this combination. Not yet fixed.
      Player-bar wiring in `layout.tsx` is a static empty-state placeholder only
      (real hookup is FE7-4/FE7-6). Add Song buttons in Nav are stubs (FE7-8).
      No page-level tests yet — flagged for FE7-9.
- [ ] FE7-6 Player Bar + Now Playing panel
- [ ] FE7-7 Drag-reorder + keyboard alt
- [ ] FE7-8 Add Song modal
- [ ] FE7-9 Coverage ≥80%
- [ ] FE7-10 Self-signed cert + nginx 80→443 redirect
- [ ] FE7-11 Multi-stage Dockerfile

### FE7-0/FE7-3 — real `pnpm install`/`pnpm test`/`pnpm build`/Docker build run, all fixed ✅

- [x] `pnpm build` ESLint failure — `.eslintrc.json` referenced `@typescript-eslint/no-unused-vars` with no matching plugin installed. Dropped the rule; `next/core-web-vitals` covers unused-vars already.
- [x] `pnpm build` TS failure — `jest.config.ts` had a typo'd `setupFilesAfterEach: []` key not in Jest's type. Removed (dead line, `setupFilesAfterEnv` already correct).
- [x] `pnpm build` failure — `postcss.config.js` used CommonJS `module.exports` but `package.json` has `"type": "module"`, so Node parsed it as ESM and crashed. Renamed `postcss.config.js` → `postcss.config.cjs`, no content change.
- [x] Static export produced no `/` page (`out/` had no `index.html`) — expected, FE7-2/FE7-5 haven't run yet, no `src/app/page.tsx` existed. Added a placeholder `src/app/page.tsx` to unblock verifying the Docker/nginx pipeline end-to-end; **real page still pending FE7-2/FE7-5**.
- [x] `docker-compose.yml`'s `ui` port mapping updated `3000:80` → `4000:80`/`4443:443` (Karthik's call — many other local Docker apps already on 80/443/3000). `nginx.conf`'s HTTP→HTTPS redirect updated to target `:4443` explicitly (`return 301 https://$host:4443$request_uri`), since the container-internal 80→443 redirect doesn't know about the host's remapped port.
- [x] `pnpm test` chain, six sequential fixes to get `src/lib/api.test.ts` green (msw@2 + Jest + pnpm's nested store layout — none obvious from a diff alone, each only surfaced by actually running the suite):
  1. `ts-node` missing — `jest.config.ts` needs it to parse a TS config file. Added as devDep.
  2. `msw/node` unresolvable — Jest's default jsdom test environment doesn't pick the right package.json `exports` condition for msw@2's conditional exports. Added `testEnvironmentOptions: { customExportConditions: [""] }`.
  3. `Request`/`fetch`/`Headers`/`Response`/`ReadableStream`/`TransformStream`/`WritableStream` all undefined in jsdom — `msw-polyfills.ts`'s comment claimed undici polyfills were wired in but the import/assign was never actually done. Added real `require()`-based polyfilling (not `import`, since ES imports hoist above other statements and undici reads `TextEncoder`/`ReadableStream` off `global` at its own module-init time — order matters here, caught by two rounds of "X is not defined" after the naive `import` version).
  4. `rettime`/`until-async`/other msw transitive deps ship pure ESM (`.mjs`/bare `export`), and Jest's default `transformIgnorePatterns` skips all of `node_modules`. `next/jest`'s wrapper also **prepends its own blanket `/node_modules/` ignore pattern and merges via OR-match**, silently defeating any custom exception passed alongside `config` — worked around by overriding `transformIgnorePatterns` on the *post-merge* result instead (`export default async () => { ...; finalConfig.transformIgnorePatterns = [...]; return finalConfig; }`), not on the pre-merge input.
  5. `BroadcastChannel` undefined in jsdom (needed by msw's WebSocket support, unused in our tests but still imported internally) — polyfilled via Node's `worker_threads`.
  - All fixes live in `ui/jest.config.ts` and `ui/src/test/msw-polyfills.ts`. `docs/FRONTEND_SETUP.md`'s "Common Gotchas" table should get an entry for #2–#5 next time it's touched — not done this session, flagged here.

### FE7-2 — component port, this session ✅

- [x] `pnpm test` 34/34 → 43/43 as FE7-5 page tests... — actually no page-level
      tests added, count grew from ConfirmDialog + playlist-path + pagination units only
- [x] `pnpm lint` clean except one `@next/next/no-img-element` warning on `Nav.tsx`'s
      sidebar logo `<img>` — same accepted tradeoff as `SongCard`'s thumbnail
      (static export's `images.unoptimized`, see below)
- [x] `SongCard`'s `<img>` → `next/image` `<Image unoptimized>` swap, to silence
      the same lint warning there. Kept `unoptimized` explicit on the element
      (not just relying on the global `next.config.mjs` setting) so it stays
      correct if this component is ever reused outside the static-export build.
- [x] `jest.config.ts`'s anonymous-default-export lint warning fixed — named the
      async config function (`jestConfig`) instead of exporting an inline arrow.
- [x] `focus-trap.ts` TS build error (`'last' is possibly 'undefined'`) — added
      non-null assertions; safe, the length check above guarantees both indices exist,
      TS just can't narrow array-index access on its own.
- [x] `msw-polyfills.ts` TS build error — `next build`'s typecheck (per `tsconfig.json`'s
      `include: ["**/*.ts", ...]`) was pulling this Jest-only file into the production
      typecheck, where its `require()`-based global polyfills collided with `lib.dom`'s
      own declarations. Fixed by excluding `src/test/**/*` in `tsconfig.json` — Jest
      doesn't consult this include/exclude list (uses `next/jest`'s own transform), so
      this doesn't affect `pnpm test`.
- [x] Stray `@typescript-eslint/no-var-requires` disable-comment removed from
      `msw-polyfills.ts` — errored because the referenced rule was never registered
      (`next/core-web-vitals` doesn't pull in `@typescript-eslint`'s plugin at all,
      same root cause as the earlier `no-unused-vars` drop). Rule was never enforced
      here, so nothing needed suppressing.
- [x] `pnpm lint` was briefly scanning `out/`'s compiled bundle output and flagging
      React internals inside minified vendor JS. Added `.eslintignore` (`out/`, `.next/`,
      `node_modules/`).

### Not yet started, flagged during FE7-3/FE7-10

- [ ] `docker-compose.yml`'s `ui` service port mapping still says `3000:80` — needs updating to `80:80`/`443:443` now that FE7-10's nginx listens on 443. Not done yet, `INFRA.md`'s port table also needs the matching update.
- **Superseded**: ports are `4000:80`/`4443:443`, not `80:80`/`443:443` (LAN box has other services on standard ports). `INFRA.md`'s port table still needs this update — not done.
- [ ] Local dev API proxy: `pnpm dev` can't reach `/api/*` standalone (no nginx in front of it). Optional `next.config.mjs` dev-only rewrite proposed in `FRONTEND_SETUP.md`, not implemented — confirm wanted before adding.
- [x] FE7-0/FE7-1/FE7-2/FE7-11 scaffold files — **confirmed installed/running for real this session**: `pnpm install`, `pnpm test`, `pnpm build`, and full `docker compose build ui` all pass. All fixes above.
- [ ] `src/app/page.tsx` is currently a one-line placeholder (`melo — placeholder`), not the real Library page — FE7-2 (components) + FE7-5 (routes) still need to build the actual page content.
- [ ] `Makefile`'s `up` target still echoes stale `http://localhost:3000` for the UI URL — should say `https://localhost:4443`. Not done, small/standalone.

## Hotfix — yt-dlp 403 (in progress)

- [ ] Confirm bumped yt-dlp (2026.8.19) actually fixes YouTube 403 — rebuild containers, resubmit real URL, check worker log for "No supported JavaScript runtime" warning
- [ ] If still 403: add `deno` JS runtime to worker Dockerfile (reverses Sprint 3's Node removal) — see `DECISIONS.md`
- [x] MinIO Docker Hub image dead — migrated `docker-compose.yml` + `tests/docker-compose.test.yml` to `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z.hotfix.7aa24e772`, verified via `make test-integration` (193/193 passed)

---

## Done

- [x] `.env.test` recreated (was missing — caused SQLite/Postgres leak across combined `make test` runs)
- [x] yt-dlp bumped `>=2026.03.17` → `==2026.8.19`
- [x] `pyproject.toml` deps switched to exact pins (`==`) repo-wide (side effect of `uv lock` re-resolution; kept deliberately)

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

- [x] Dropdown: close on `Escape` — `closeOpenDropdown()` in `app.js`, slotted into `handleKeydown`'s Esc chain (panel → dropdown → modal)
- [x] Modal: manual focus trap (`trapFocus()`, wraps `Tab`/`Shift+Tab` on `.modal` focusables)
- [x] Now Playing panel: same focus trap extended to it — new surface, wasn't in original ticket list (written pre-FE-3), added this session. See DECISIONS.md.
- [x] `#toast-root`: `aria-live="polite"` added in `index.html`
- [x] Status pill: `aria-label="Status: {status}"` added, dot marked `aria-hidden`
- [x] Dropdown: `aria-haspopup`/`aria-expanded` on trigger, kept in sync on open/close/outside-click/Escape. Menu/items are native buttons, no `role="menu"`/`"menuitem"` (post-sprint fix — see `DECISIONS.md`)- [ ] Manual tab-order pass across all pages incl. FE-0-FE-3 markup — still needs an actual browser, ask Karthik
- [x] Playlist drag-reorder keyboard alt — Karthik's call: fix now. Rows focusable (`tabindex="0"`), Arrow Up/Down calls the same `reorderPlaylistSongOptimistic()` path drag uses, focus restored to the moved row after re-render. `aria-label` states position/total; sr-only hint states the key binding.

### FE-5 — UX Bug Fixes (ongoing, audit-driven)

- [x] Playlist Detail row: song card wasn't stretching full width — `.playlist-song-row` is row-flex (no stretch by default), unlike Library's column-flex `.song-list`. Fixed: `.playlist-song-row .song-card { flex: 1; min-width: 0; }`
- [x] Player Bar + Now Playing panel scrubber/volume slider had no progress-fill color — both were flat `--bg-elevated`. Fixed: `--progress` CSS var set on every tick, `linear-gradient` in `style.css`
- [x] Now Playing panel waveform didn't indicate playback position — bars now recolor played/unplayed on each `timeupdate` tick
- [x] Now Playing panel scrubber: seeking to a new position and resuming playback snapped back to the pre-seek time. Root cause found in two passes — first, `change`/`mouseup`/`touchend` handlers could race; second (regression introduced fixing the first), a stray undefined `scrubber` reference in `player.js`'s `seekTo()` threw silently. Both fixed; **needs Karthik re-confirm**, not retested after 2nd fix
- [x] Now Playing panel volume icon misaligned above slider — `.player-volume` was missing `display:flex`
- [x] Playlist grid card delete (✕) button rendered at bottom of card instead of top-right — added `position:relative`/`absolute`
- [x] Player Bar showed nothing when no song loaded — added placeholder icon+text, toggled via existing `.player-bar--empty` state
- [x] Player Bar: shuffle button moved to sit next to loop button (pure DOM reorder in `index.html`; Now Playing panel's shuffle/loop order deliberately left as-is)
- [x] Custom favicon + sidebar logo mark wired in (`ui/assets/logo.png`, Karthik-generated)

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

## Post-Sprint 6 — CodeRabbit Review Fixes

Backend + frontend findings from an automated review pass, worked one-by-one against actual code (not assumed from the finding text alone).

- [x] `app/api/playlists.py`: `DELETE .../songs/{song_id}` left `position` gaps after removal — later `PATCH` reorders (which treat `position` as a list index) could land on the wrong song. Added `_compact_positions()`, called after delete/before commit. Regression test: `test_reorder_after_delete_compacts_positions`.
- [x] `ui/player.js`: `toggleShuffle()` mutated `queue` in place with no stored original order — disabling shuffle left the queue permanently scrambled. Added `originalQueue`, restored on disable (current song kept in place, same pattern as enable).
- [x] `ui/app.js`: `playSongById()` silently no-op'd if `id` fell out of `state.currentSongList` (race with poll/filter refresh between render and click). Now falls back to `loadSongDirectly()` (fetches + `player.loadSong()`, toast on failure).
- [x] `ui/app.js`: Now Playing panel's document-level `mouseup`/`touchend` scrubber-commit listeners were never removed on close — accumulated on every reopen. Tracked via `state.npCommitSeekHandler`, removed in `closeNowPlayingPanel()`.
- [x] `ui/app.js`: Reopening the Now Playing panel could flash the *previous* song's waveform for one frame — `player.subscribe()`'s synchronous initial callback ran before `loadAndDrawWaveform()` cleared `state.npPeaks`. Now cleared in `closeNowPlayingPanel()` too, so the next open starts from `null`.
- [x] `ui/style.css`: dead `.sidebar__logo-icon` rule (class doesn't exist in `index.html`) removed — was accidentally suppressing nothing, but flagged as hiding the logo mark at desktop, which would have contradicted `DESIGN.md`'s "shown at all sidebar-visible breakpoints" spec had it matched anything.
+- [x] `tests/smoke_ui.sh` FE-2 section (~line 165): comment was ambiguous about which case (unknown-membership 404 vs out-of-range 422) is under test. Fixed — split into two comments, each scoped to its own check.
+- [x] `app/api/playlists.py` reorder endpoint: `API_DOC.md`'s "no concurrent-write race window" claim was false — no row lock was taken before reading membership/count. Added `_lock_playlist_songs()` (`SELECT ... FOR UPDATE`) ahead of the membership/count read, same transaction as the shift. `API_DOC.md` updated to describe actual locking/contention behavior instead of claiming no race window.
- Concurrency integration test attempted, then removed: the `db_session` fixture's savepoint-rollback pattern means separate connections can't see each other's uncommitted rows, so a real cross-connection lock-contention test isn't constructible against it. Flagged as backlog if real coverage is wanted later (needs a commit-visible fixture, e.g. the `_truncate_all()` pattern).
- [x] `tests/smoke_test.sh` S8: 502 handling now checks whether the song hit the dedup path (`DEDUP_HIT`, from S7's `ELAPSED <= 5` signal) before attributing the failure to DB/MinIO volume drift. Non-dedup 502s now point at presigning/streaming/FFmpeg instead. Destructive `make down-v` recovery step now explicitly warns it wipes data and suggests `make backup` first.
- [x] `tests/smoke_test.sh` S17: "unknown membership" reorder check was actually testing an unknown *song* (`00000000-...` doesn't exist, hits `_get_song_or_404`, not the membership check). Added a real song (song D) that exists but isn't a playlist member, to actually exercise `_get_membership_or_404`; deleted immediately after.
- [x] `ui/components.js`: `aria-haspopup`/`aria-expanded` were on the `.song-card` (`role="listitem"`) wrapper instead of the `[data-action="open-menu"]` trigger button. Moved to the button. Verified `app.js`'s three `aria-expanded` sync sites (toggle click, outside-click, `closeOpenDropdown()`) already targeted the button correctly — no knock-on fix needed there.
- [x] `CHANGELOG.md` 0.6.0: "sentinel-position swap" → "sentinel-position shift" (mechanism is a shift of intermediate rows, not a two-item swap — matches the "shift-not-swap" test already in the suite).
- [x] `docs/PRD.md`: FE-2 reorder behavior/status table updated to describe the sentinel-based shift (both directions) and drop the stale `IntegrityError`-retry/`409` language; FE-5's `TODO.md`-empty claim changed to past tense; `smoke-ui.sh` → `tests/smoke_ui.sh`; FE-3 dependency table corrected from "player bar" to "Now Playing panel".
- [x] `docs/DECISIONS.md`: fixed a self-contradiction — the playlist-keyboard-reorder row said "logged, not fixed this ticket" while the adjacent row and actual code (`handlePlaylistRowKeydown`/`reorderPlaylistSongOptimistic` in `app.js`) show it was fixed same-sprint. Corrected to match.
- [x] `ui/components.js`: song dropdown used `role="menu"`/`role="menuitem"` with no matching keyboard model (no arrow-key nav, no roving focus/tabindex, no menu-specific Enter handling — items are plain buttons handled via existing click delegation). Mismatched ARIA role, screen readers announced menu semantics the widget didn't back up. Fixed by dropping both roles, kept native button behavior (Tab/Enter/Space/Escape already worked). `aria-haspopup`/`aria-expanded` on the trigger left as-is — valid for a button-triggered disclosure regardless of menu role.
- Reviewed, already correct, no change needed: playlist-row aria-label total (already threaded through `songs.length`, not `state.currentSongList.length`), `.sr-only` (`clip-path` not deprecated `clip`), `#player-info-trigger` keydown (`stopPropagation` present), `.player-bar--empty` (already hides shuffle/loop/volume), `handleEnded` (already skips non-`done` queue entries via `findNextPlayableIndex`), `getPeaks` (already caches the in-flight promise, not just the resolved value), `.player-volume` (`display: flex` already scoped to `min-width: 768px`).
- [x] `ui/app.js`: `reorderPlaylistSongOptimistic()` comment clarified — describes move-to-final-index semantics (splice out at `oldIndex`, insert at `newPosition` — lands after target moving down, before target moving up). No logic change.
- [x] `README.md`: removed `waveforms` from the "Out of Scope (v1) — never" list — waveform display shipped in Sprint 6; only click-to-seek remains a Sprint 7+ candidate, already listed separately.
- [x] `tests/smoke_test.sh` (~L491-492): add-to-playlist `api_post` calls now check return status and call the existing fail handler on failure, matching the song-creation checks — a silent add-song failure was previously masked until the later ordering assertion.
- [x] `tests/smoke_test.sh` (~L529-532): PATCH-with-nil-UUID-playlist labels corrected from "unknown song" to "unknown playlist" — request/expected-404 behavior unchanged, wording only.
- [x] `tests/smoke_ui.sh` (L183): jq-missing skip message now lists all skipped checks (create, get, cleanup, add-unknown-song, remove-unknown-song, both FE-2 reorder checks) instead of a generic message.
- [x] `ui/app.js`: Now Playing panel — overlay marked `role="dialog"`/`aria-modal="true"`; `openNowPlayingPanel()` guards against re-opening while already open; focus moves to the panel's first focusable element on open (so `trapFocus` has somewhere to start) and returns to `#player-info-trigger` on close.
- [x] `ui/app.js`: `drawWaveform()` — `barWidth` guarded against going negative when `peaks.length` exceeds canvas width (gap derived responsively from available width/peak count); bars stay visible on narrow canvases instead of collapsing/inverting.
- [x] `ui/style.css`: `.player-volume` base rule now sets `display:flex; flex-direction:row` directly instead of relying on a separate `@media (min-width:768px)` override — removed the redundant display rule; `.player-ctrl-wide`'s phone-hide behavior untouched.

---

## Sprint 7+

Not scoped yet. Candidates already known but deferred:

- Waveform click-to-seek
- Bulk/multi-select playlist reorder
- Fix drag-preview showing only thumbnail (cosmetic, `draggable="false"` on `.song-card__thumb`) — deferred from FE-5, see flagged item above
- Multi-user auth, Alembic -- still explicitly out of scope, not just deferred
