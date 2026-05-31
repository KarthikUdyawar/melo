# Melo — Sprint 4: Vanilla JS UI

**Duration:** Week 4
**Goal:** Ship a minimal, clean vanilla HTML/JS/CSS SPA covering the full user journey: add → process → play → organize.
**Branch strategy:** `develop` base → feature branches → PR → CodeRabbit review → merge
**UI location:** `ui/` (same repo, separate Docker service)

---

## Sprint Goal

> *A user can open `http://localhost:3000`, paste a YouTube URL, watch it process, play it back, mark favorites, and organize into playlists — without touching the terminal.*

---

## Why Vanilla JS

- Zero build step → 2-second Docker build (nginx just copies files)
- No Node, no pnpm, no lockfile hell, no WSL memory pressure
- `<audio>` element gives full player control natively
- ES modules (`<script type="module">`) for clean separation
- All DESIGN.md tokens applied directly via CSS custom properties

---

## File Structure

```text
ui/
  index.html        # app shell, Google Fonts, script imports
  style.css         # all design tokens + component styles + animations
  api.js            # fetch wrappers — envelope unwrap, all endpoints
  player.js         # audio element, player state, scrubber sync
  components.js     # renderSongCard, renderStatusPill, renderModal, renderToast
  app.js            # hash router, page renderers, polling logic
  nginx.conf        # SPA fallback + /api/ proxy to api:8000
  Dockerfile        # FROM nginx:alpine, COPY files, done
```

---

## Backlog

---

### ✅ UI-0 — Scaffold & Docker Integration

#### Files
* [x] `ui/index.html` — app shell: sidebar + main + player bar divs, Google Fonts link, module script imports
* [x] `ui/style.css` — all CSS vars from DESIGN.md, layout grid, base resets
* [x] `ui/api.js` — `apiFetch(path, init)` envelope unwrap + all typed wrappers (14 endpoints)
* [x] `ui/player.js` — `loadSong(song)`, `play()`, `pause()`, `togglePlayPause()`, `isSongLoaded()`
* [x] `ui/components.js` — `renderSongCard`, `renderStatusPill`, `renderPlaylistCard`, `renderToast`
* [x] `ui/app.js` — hash router: `#/`, `#/favorites`, `#/playlists`, `#/playlists/:id`

#### Docker
* [x] `ui/Dockerfile` — `FROM nginx:alpine`, 3 lines, ~2s build
* [x] `ui/nginx.conf` — SPA fallback + `/api/` proxy → `http://api:8000`, `proxy_buffering off`
* [x] `docker-compose.yml` — `ui` service on port 3000

#### App Shell
* [x] Sidebar: logo, nav links (Library / Favorites / Playlists), [+ Add Song] button
* [x] Main: `<div id="page-content">` — swapped by router
* [x] Player bar: always visible at bottom, hidden state when no song loaded (`player-bar--empty`)

#### Bugs fixed post-merge
* [x] `handleGlobalClick` early `return` blocked song card clicks — fixed by moving card/playlist checks above action guard
* [x] Worker `/tmp/melo` permission denied — fixed via `tmpfs` in docker-compose

---

### ✅ UI-1 — Library Page

#### `renderStatusPill(status)` in `components.js`
* [x] `pending` → grey dot + "pending"
* [x] `processing` → yellow pulsing dot + "processing"
* [x] `failed` → red dot + "failed"
* [x] `done` → returns `""` (no pill)

#### `renderSongCard(song, isPlaying)` in `components.js`
* [x] Thumbnail (48×48) · title + channel · duration · heart icon · status pill · overflow menu (⋮)
* [x] `isPlaying` → accent left border + accent title color
* [x] Hover → `--bg-elevated` (CSS handles via `:hover`)
* [x] Returns HTML string; caller sets `innerHTML`

#### Library page in `app.js`
* [x] `renderLibraryPage()` — fetches `GET /songs`, renders song list
* [x] Filter bar: search input (300ms debounce), status dropdown, sort dropdown
* [x] "Load more" button — cursor pagination via `bookmark`
* [x] Auto-poll: `setInterval` 2s while any song `pending`/`processing`; `clearInterval` when all `done`/`failed`
* [x] Empty state: "No songs yet." + [Add Song] button
* [x] Click song card → `player.loadSong(song)`
* [x] Active card: DOM update on play (not full re-render)
* [x] **Retry button on failed song cards** — `renderRetryButton` in `components.js`, `handleRetrySong` in `app.js`

---

### ✅ UI-2 — Add Song Modal

**Step 1 — URL input:**
* [x] Full-screen overlay with URL `<input>` + [Preview] button
* [x] [Preview] disabled when input empty
* [x] On submit → calls `api.previewSong(url)`
* [x] Inline error on failure (re-renders step 1 with error message, URL preserved)
* [x] **Loading spinner during preview fetch** — `buildStep1LoadingHtml` + `spinnerSvg()`, input disabled while fetching

**Step 2 — Confirm + params:**
* [x] Thumbnail, title, channel, duration display
* [x] `start` input (seconds, optional)
* [x] `end` input (seconds, optional)
* [x] `speed` select: `0.5× / 0.75× / 1.0× / 1.25× / 1.5× / 2.0× / 4.0×`
* [x] [Cancel] closes modal
* [x] [Add to Melo] → calls `api.submitSong(...)` → closes modal → re-renders library

---

### ✅ UI-3 — Player Bar

#### `player.js`
* [x] Single `<audio>` element (module-scope, not in DOM)
* [x] `loadSong(song)` — sets `audio.src`, updates player bar UI, calls `audio.play()`
* [x] `play()` / `pause()` / `togglePlayPause()`
* [x] `getCurrentSong()` / `isSongLoaded(id)` / `isPlayingSong(id)`
* [x] `onTimeUpdate` — syncs scrubber with `audio.currentTime`
* [x] `onEnded` — resets play button + scrubber

#### Player bar HTML
* [x] Left: thumbnail (40×40) + title + channel
* [x] Center: play/pause button + scrubber range + timestamp
* [x] Hidden class when no song loaded (`player-bar--empty`)
* [x] Only plays when `song.status === "done"`

#### Seeking — fixed
**Root cause:** `GET /songs/{id}/stream` returned `200 OK` without `Accept-Ranges`. Browser treated stream as non-seekable.

**Fix (`app/api/songs.py`):**
- No trim/speed → `httpx` proxies MinIO internally, forwards browser `Range` header → `206 Partial Content`
- Trim/speed → `FileResponse` (Starlette handles ranges natively)
- Verified working in UI (speed + trim audio confirmed)

---

### ✅ UI-4 — Favorites Page

#### Favorite toggle (in song card)
* [x] Heart icon: filled SVG when `is_favorite`, outline when not
* [x] Click → `api.addFavorite(id)` or `api.removeFavorite(id)`
* [x] Optimistic flip: toggle class immediately, revert on error

#### Favorites page in `app.js`
* [x] `renderFavoritesPage()` — fetches `GET /favorites`, renders same song card list
* [x] Empty state: "No favorites yet."

---

### ✅ UI-5 — Playlists

#### `renderPlaylistCard(playlist)` in `components.js`
* [x] Name, song count
* [x] Click → navigate to `#/playlists/:id`

#### Playlists page in `app.js`
* [x] `renderPlaylistsPage()` — fetches `GET /playlists`, renders grid
* [x] [+ New Playlist] button → inline `<input>` → Enter/Create → `api.createPlaylist(name)` → re-render
* [x] Empty state: "No playlists yet."

#### Playlist detail page in `app.js`
* [x] `renderPlaylistDetailPage(id)` — fetches `GET /playlists/:id`
* [x] Ordered song list with position number + song card
* [x] Remove button per row → `api.removeSongFromPlaylist(...)` → re-render

#### "Add to playlist" overflow menu (⋮) in song card
* [x] Dropdown: all playlists + [+ New playlist]
* [x] Select → `api.addSongToPlaylist(...)` → toast confirmation
* [x] [+ New playlist] → `window.prompt()` → create + add

---

### ✅ UI-6 — Polish & Integration

* [x] `renderToast(message, type)` — slide-up, 3s auto-dismiss, success + error variants
* [x] Delete song: confirm dialog → `api.deleteSong(id)` → remove from list + clear player bar
* [x] Health check on load: `GET /health` → banner if API unreachable
* [x] `document.title` per route
* [x] Keyboard: `Space` = play/pause, `Esc` = close modal
* [x] `aria-label` on all icon-only buttons
* [x] Focus rings on all interactive elements (CSS `:focus-visible`)
* [x] Failed song card: [Retry] button → deletes old record + re-submits same URL/params
* [x] "Load more" null-check fix — hides button when `records.length < limit` even if bookmark non-null
* [x] Active card highlight — page renders now pass `s.id === currentSongId` for correct initial state
* [x] Removed debug `console.log` from `app.js`
* [x] Loading spinner in preview step 1

---

## Definition of Done

* [x] `docker compose up` starts `ui` at `http://localhost:3000`
* [x] Full add → process → play flow works end-to-end
* [x] Library filter + search + pagination works
* [x] Favorites toggle works and persists
* [x] Playlists create + add song + view ordered + remove song works
* [x] Player bar persists across page navigation (hash routing)
* [x] Seeking works (httpx proxy forwards Range header → 206; FileResponse for processed audio)
* [x] No console errors in happy path
* [x] DESIGN.md tokens applied via CSS vars (no raw hex in CSS)
* [x] `README.md` updated: UI section, `make up` note, port table

---

## Clean Code Contract

Per the clean-code skill, every JS module must:

- Do one thing (`api.js` fetches, `player.js` plays, `components.js` renders, `app.js` routes)
- Intention-revealing names (`loadSong` not `set`, `renderStatusPill` not `pill`)
- Functions under 20 lines
- No logic in render functions — extract to named helpers
- No global mutable state except `player.js` (intentional — single audio element)

---

## Decision Log

| Decision                                 | Reason                                                                                                                |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Vanilla JS over React/Vue                | Zero build step; no Docker memory pressure; no WSL disconnect risk                                                    |
| ES modules (`type="module"`)             | Clean imports without bundler; supported in all modern browsers                                                       |
| Hash routing (`#/`)                      | No server config needed for SPA; nginx serves `index.html` for all                                                    |
| Single `<audio>` element in DOM          | Persistent player across page nav; no framework state needed                                                          |
| HTML strings + `innerHTML`               | Simple, fast; no virtual DOM needed at this scale                                                                     |
| `setInterval` for polling                | Sufficient for 2s poll; no RxJS/query library overhead                                                                |
| nginx proxies `/api/` → `api:8000`       | Same pattern as before; CORS-free in prod                                                                             |
| No frontend tests                        | No framework = no component test surface; API already tested                                                          |
| Dockerfile = 3 lines                     | `FROM nginx:alpine` + `COPY` + `CMD`; builds in ~2s                                                                   |
| Event delegation via `handleGlobalClick` | Single listener on `document`; works for dynamically rendered cards                                                   |
| Card click checks before action guard    | Prevents early `return` from blocking song card play on non-action clicks                                             |
| `httpx` proxy for stream (no trim/speed) | Presigned URL redirect breaks Sig V4 when internal/external hostnames differ; proxy forwards Range header server-side |
| `FileResponse` for processed audio       | Starlette native range support; `BackgroundTask` handles tmp cleanup post-response                                    |
| Retry = delete + resubmit                | No retry endpoint in API; preserves original params (start/end/speed) from existing song record                       |
| Spinner via `buildStep1LoadingHtml`      | Separate loading template keeps `buildStep1Html` pure; input disabled prevents double-submit                          |
| `hasMore = bookmark && records >= limit` | Partial page means end of results even if backend returns a bookmark; prevents ghost "Load more"                      |
