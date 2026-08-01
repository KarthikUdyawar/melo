# Melo — Frontend Design Spec

> Simple. Minimal. Dark. Focused on music.

---

## Design Philosophy

**Direction:** Refined dark minimalism — like a personal tool built by someone who cares.
Not a SaaS product. Not a landing page. A quiet, focused app that gets out of your way.

**One sentence:** *A dark room with a record player in the corner.*

**Principles:**
- Content first. Chrome last.
- One thing on screen at a time where possible.
- No unnecessary color. Let the thumbnails be the art.
- Interactions feel immediate and physical — not floaty.

---

## Color

```css
--bg-base:       #0e0e0e;   /* near-black canvas */
--bg-surface:    #161616;   /* cards, modals, sidebars */
--bg-elevated:   #1f1f1f;   /* hover states, inputs */
--border:        #2a2a2a;   /* subtle dividers */

--text-primary:  #f0f0f0;   /* headings, active labels */
--text-secondary:#8a8a8a;   /* metadata, captions */
--text-muted:    #484848;   /* placeholders, disabled */

--accent:        #c8f04e;   /* acid lime — the one pop of life */
--accent-dim:    #8aaa2a;   /* hover/pressed accent */
--danger:        #e05252;   /* delete, error states */

--player-bg:     #111111;   /* persistent player bar */
```

Single accent color. No gradients except the scrubber/volume progress-fill (Sprint 6 — see Player Bar below), which reads `--accent` against `--bg-elevated`. No decorative illustrations. Thumbnails from YouTube are the main "color" in the UI, alongside the app logo.

---

## Typography

```
Display / Headings:  "Syne"         — geometric, slightly quirky, strong
Body / UI:           "DM Mono"      — monospaced, clean, feels like a tool
```

Both from Google Fonts — loaded via `<link>` in `index.html`.

```css
--font-display: 'Syne', sans-serif;
--font-body:    'DM Mono', monospace;

--text-xs:   11px;
--text-sm:   13px;
--text-base: 15px;
--text-lg:   18px;
--text-xl:   24px;
--text-2xl:  32px;

--leading:   1.6;
--tracking:  0.01em;
```

All metadata (duration, date, channel) uses monospaced — feels like file system info.

---

## Spacing & Layout

8px base unit. Multiples of 8.

```css
--space-1:   4px;
--space-2:   8px;
--space-3:  12px;
--space-4:  16px;
--space-6:  24px;
--space-8:  32px;
--space-12: 48px;
--space-16: 64px;

--radius-sm:  4px;
--radius-md:  8px;
--radius-lg: 12px;
```

### App Shell — responsive, mobile-first (Sprint 6, FE-0)

**As of Sprint 6, Melo supports three breakpoint tiers, overturning the earlier Sprint-4 desktop-only decision** (Karthik's call — personal use expanded to phone). CSS Grid throughout, mobile-first base styles with `min-width` media queries layering on tablet/desktop.

```css
--sidebar-width-desktop: 220px;
--sidebar-width-tablet:  56px;
--player-bar-height:     72px;
--tab-bar-height:        56px;
```

| Tier    | Width      | Nav                                                                      | Notes                                    |
| ------- | ---------- | ------------------------------------------------------------------------ | ---------------------------------------- |
| Phone   | <=767px    | Bottom tab bar (Library/Favorites/Playlists) + floating **Add Song** FAB | Sidebar fully hidden; single-column grid |
| Tablet  | 768–1279px | Sidebar collapses to a 56px icon rail, no drawer/hamburger               | Spotify-style icon-only nav              |
| Desktop | >=1280px   | Full 220px sidebar with labels                                           | Original Sprint-4 layout, unchanged      |

```css
/* Phone (base) */
body {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: 1fr var(--player-bar-height) var(--tab-bar-height);
  height: 100vh;
}

/* Tablet */
@media (min-width: 768px) {
  body {
    grid-template-columns: var(--sidebar-width-tablet) 1fr;
    grid-template-rows: 1fr var(--player-bar-height);
  }
}

/* Desktop */
@media (min-width: 1280px) {
  body { grid-template-columns: var(--sidebar-width-desktop) 1fr; }
}
```

- CSS-only breakpoint switching — no JS layout logic beyond the tab-bar/sidebar visibility toggle inherent in the media queries themselves.
- `.sidebar` is `display:none` on phone; icon rail (centered icons, no labels) at 768px; labels revealed at 1280px via `.nav-link__label`/`.sidebar__logo-full` display toggles.
- Modal is full-screen (no radius, no backdrop margin) below 768px; centered floating card (unchanged Sprint-4 look) at 768px+.
- Song card stacks (thumbnail top, title/meta/actions below) on phone; unchanged horizontal row at 768px+.

---

## Components

### Logo (Sprint 6, this session)

Custom AI-generated mark, `ui/assets/logo.png` — lime music-note glyph on a dark rounded-square tile, matching `--accent`/`--bg-base`. Used as:
- Favicon (`<link rel="icon" type="image/png" href="assets/logo.png">`)
- Sidebar mark (`<img class="sidebar__logo-mark">`, 28×28, `--radius-sm`), shown alongside the `melo` wordmark at all breakpoints where the sidebar is visible

### Song Card

Horizontal layout at tablet/desktop (thumbnail left, title + metadata right, actions far right); stacks vertically on phone (thumb top, then title/meta, then a full-width actions row).

```
┌──────────────────────────────────────────────────────┐
│  [thumb]  Title of the Song              03:32  ♡  ⋮  │
│           Channel name · 2022                         │
└──────────────────────────────────────────────────────┘
```

- Active/playing song: left border 2px `--accent`, title color `--accent`
- Hover: `--bg-elevated` background (CSS `:hover`)
- Status pill inline for `pending` / `processing` / `failed`
- Failed songs show an inline **Retry button** (`.btn--retry`, `↺ Retry`) next to the status pill — outlined in `--danger`, resubmits via `POST /songs`
- Rendered as HTML string by `renderSongCard()` in `components.js`
- **Playlist Detail context (fixed this session):** when nested inside a `.playlist-song-row`, the card gets `flex: 1; min-width: 0` so it fills the row's full width — a row-flex parent doesn't stretch children the way Library's column-flex `.song-list` does by default, so this override is required specifically for the playlist-row wrapper.

### Overflow Menu (Song Card `⋮`)

Dropdown anchored to the song card's `⋮` icon button (`.dropdown` / `.dropdown__menu`), opened/closed via click and closed automatically on outside click **or `Escape`** (Sprint 6, FE-4 — `closeOpenDropdown()`, slotted first in the Escape-priority chain: Now Playing panel → dropdown → modal).

```
┌────────────────────────┐
│  Morning Mix           │
│  Focus                 │
│  + New playlist        │
│  ─────────────────     │
│  Delete                │
└────────────────────────┘
```

- Lists existing playlists (add song to playlist), then a `+ New playlist` entry, then a divider, then a destructive **Delete** item (`--danger` color)
- Positioned `absolute`, right-aligned under the trigger, fades in 80ms
- Rendered inline as part of `renderSongCard()` — not a separate component function
- `aria-haspopup`/`aria-expanded` on the trigger button, kept in sync across open/close/outside-click/Escape (Sprint 6, FE-4). Menu and items are plain native `<button>`s with no `role="menu"`/`"menuitem"` — those roles imply arrow-key navigation and roving focus the widget never implements (Tab/click/Escape handle it instead); see `DECISIONS.md`.

### Player Bar

Fixed bottom, full width at tablet/desktop. Compacts on phone to thumb + title + play/pause + scrubber only (prev/next, time labels, loop, volume, shuffle hidden via `.player-ctrl-wide`).

```
┌─────────────────────────────────────────────────────────┐
│  [thumb] Title     ◀  ▶  ━━━━━●━━━━  00:42 / 03:32 ⤨ ↻ │
│          Channel                                  🔊━━● │
└─────────────────────────────────────────────────────────┘
```

- Single `<audio>` element in DOM, module-scoped in `player.js` — persists across page navigation
- **Progress bar (`.player-scrubber`, `<input type="range">`)**: filled with `--accent` up to playhead, `--bg-elevated` after, via a `--progress` CSS custom property set from JS (`linear-gradient` background reading the var). Range inputs have no CSS-only way to reflect their own live value, so `--progress` is pushed on every `input`/`timeupdate` tick — same pattern used on the volume slider and mirrored in the Now Playing panel.
- `player.js` syncs scrubber position + fill via `audio.ontimeupdate`; dragging the scrubber suppresses the tick handler until released
- **Click/drag scrubber to seek** — works in both the bar and the Now Playing panel
- Hidden info/controls (via `visibility:hidden`, box space preserved) when no song loaded, replaced by a **placeholder** (`.player-bar__placeholder`, icon + "No song playing — pick one from your library") — added this session so the bar isn't blank on first load
- Title/channel swap instantly on song change — no transition applied (see Motion table)
- **Control order (phone hidden, tablet/desktop shown):** info/thumb → shuffle → prev/play-pause/next + scrubber + time → loop → volume. Shuffle was moved to sit immediately left of the loop button this session (previously between info and the transport cluster); this reorder is Player-Bar-only — the Now Playing panel keeps its own separate control order (see below).
- **Shuffle**: session-only (not persisted), Fisher–Yates reshuffle keeping the current song in place, `aria-pressed` state
- **Loop**: single 3-state icon button (`data-mode="off"|"one"|"all"`), cycles off → one → all, persisted to `localStorage['melo:loop']`. Badge overlay ("1") shows only in loop-one state — CSS selector is the shared `.loop-btn[data-mode="one"]` class (not an ID selector), so the same rule covers both the Player Bar's `#btn-loop` and the Now Playing panel's `#np-loop`
- **Volume**: slider + mute-toggle icon button, persisted to `localStorage['melo:volume']`, default `1.0`, remembers pre-mute level on unmute
- **Prev/Next**: operate on the current queue (built from whichever song list was on screen when a card was clicked), skip non-`done` entries. `prev()` restarts the current song if >3s played, otherwise jumps to the previous track (standard media-player convention)

### Now Playing Panel (Sprint 6, FE-3)

Full-screen overlay opened by tapping the Player Bar's thumbnail/title (`#player-info-trigger`, `role="button"`, Enter/Space accessible). New UI surface — not part of the original Sprint-4 design.

```
┌───────────────────────────────┐
│                            ✕  │
│         [large thumbnail]     │
│         Title of the Song     │
│         Channel               │
│                                │
│  ▁▂▄▇▅▃▂▁▃▅▇▆▄▂▁  (waveform)  │
│                                │
│    ⤨   ◀   ▶▮▮   ▶   ↻        │
│  ━━━━━━●━━━━━━  00:42 / 03:32 │
│         🔊 ━━━━●━━            │
└───────────────────────────────┘
```

- Large thumbnail, title, channel, waveform canvas, transport controls (shuffle, prev, play/pause, next, loop — **same set as the Player Bar but panel-local control order is unchanged from FE-3's original ticket**, i.e. this session's Player-Bar-only shuffle reorder does *not* apply here), scrubber, volume, close button
- State (play/pause, scrubber position, time, volume, shuffle, loop mode, current song) mirrors the Player Bar live via a `subscribe()` pub-sub in `player.js` — the panel doesn't own its own timers, it just listens
- **Waveform**: fetched as `ArrayBuffer` on first play, decoded via `AudioContext.decodeAudioData()`, downsampled to ~200 peak buckets, rendered to `<canvas>`. Peaks cached in-memory per session (`Map<songId, peaks>`, module-scoped in `player.js` so the cache survives panel close/reopen and hash navigation — no persistence across reloads).
- **Waveform playback coloring (this session)**: bars before the current playhead render in `--accent`, bars after in `--bg-elevated` — redrawn on every `timeupdate` tick against the cached peaks. Click-to-seek on the waveform itself is explicitly out of scope (the separate scrubber control below it handles seeking).
- **Scrubber seek**: click/drag to seek, mirrors the Player Bar's scrubber but tracked with its own independent drag-state flag (`state.npSeeking` in `app.js`) — two scrubbers on two surfaces can't share one seeking flag without one interrupting the other. Seek commit is unified into a single `commitSeek()` function guarded by that flag, fired from whichever of `change`/`mouseup`/`touchend` lands first (fixed this session after a race between separate handlers left seeks silently uncommitted).
- **Volume slider + icon**: same `--progress` fill pattern as the Player Bar; icon sits centered above the slider (`display:flex` on `.player-volume`, fixed this session — was previously misaligned).
- Manual focus trap (`trapFocus()`, shared with `.modal` — takes the container as a param) wraps `Tab`/`Shift+Tab` across the panel's focusable set (close button, transport, 2 sliders)
- `Escape` closes the panel first in the priority chain (panel → dropdown → modal)

### Add Song Modal

Full-screen overlay below 768px (no radius, no backdrop margin — app-sheet feel); centered floating card at 768px+ (unchanged Sprint-4 look). Two-step flow managed in `app.js`. Built via inline HTML-string builders (`buildStep1Html`, `buildStep1LoadingHtml`, `showStep2`) — there is no `renderModal()` helper in `components.js`.

**Step 1 — URL input:**
```
┌─────────────────────────────────────┐
│  Paste YouTube URL                  │
│  ┌─────────────────────────────┐    │
│  │ https://youtube.com/...     │    │
│  └─────────────────────────────┘    │
│                          [Preview]  │
└─────────────────────────────────────┘
```
- Inline error text (`.modal__error`) appears under the field on invalid URL or a failed preview fetch (e.g. 422/502 from `POST /songs/preview`), and the field/button re-enable for retry.

**Step 1 (loading) — while metadata fetches:**
```
┌─────────────────────────────────────┐
│  Paste YouTube URL                  │
│  ┌─────────────────────────────┐    │
│  │ https://youtube.com/... (disabled)
│  └─────────────────────────────┘    │
│                    [⟳ Fetching…]    │
└─────────────────────────────────────┘
```
- URL input disabled, submit button replaced with a spinner (`.spinner`, CSS `spin` keyframe, 0.8s linear infinite) + "Fetching…" label.

**Step 2 — Preview + params:**
```
┌─────────────────────────────────────┐
│  [thumb]  Title of Song             │
│           Channel · 3:32            │
│                                     │
│  Start  [______]  End  [______]     │
│  Speed  [  1.0×  ▼  ]               │
│                                     │
│  [Cancel]            [Add to Melo]  │
└─────────────────────────────────────┘
```

- Modal open/close: opacity + `scale(0.97→1)`, 120ms
- `Esc` closes modal (keydown listener in `app.js`, last in the panel → dropdown → modal priority chain)
- On phone, opened via either the sidebar's Add Song button (hidden on phone) or a floating **FAB** (`.fab-add`, bottom-right, above the tab bar) — both share the `.btn-add-song-trigger` class so one modal-open handler serves both entry points without an id collision

### Confirm Dialog

Reused for both **Delete Song** and **Delete Playlist** — same modal shell (`.modal.confirm-dialog`), centered text, destructive confirm button.

```
┌─────────────────────────────────────┐
│           Delete Song                │
│  Delete this song? This cannot be   │
│  undone.                             │
│                                       │
│  [Cancel]              [Delete]      │
└─────────────────────────────────────┘
```

- `[Delete]` uses `.btn--danger`
- Built inline via `confirmDeleteSong()` / `confirmDeletePlaylist()` in `app.js`, not a shared component function

### Status Pill

```
pending    →  grey    •  "pending"
processing →  yellow  •  "processing"  (pulse animation on dot)
done       →  (no pill — implicit)
failed     →  red     •  "failed"
```

Rendered by `renderStatusPill(status)` in `components.js`. Returns empty string for `done`. `aria-label="Status: {status}"` on the pill, dot marked `aria-hidden` (Sprint 6, FE-4).

### Sidebar Nav

Desktop (>=1280px, full labels shown):
```
  [logo] melo

  Library
  Favorites
  Playlists

  [+ Add Song]   ← accent button, bottom of sidebar
```

Tablet (768–1279px): same structure, icon-only (56px rail, no labels, no drawer/hamburger — Spotify-style, Karthik's call).

Phone (<=767px): sidebar hidden entirely; replaced by a bottom tab bar (`.tab-bar`, same 3 routes) plus a floating Add Song FAB (see Add Song Modal above).

- Icon + label nav links (icons added Sprint 6 — plain text-only links were the original Sprint-4 design). Active link detected via `window.location.hash`. Active: left border 2px `--accent` (bottom-tab-bar variant: `--accent` text color, no border), text `--text-primary`. Inactive: `--text-secondary`.

### Toast

Slides up from just above the player bar (`bottom: 88px` at tablet/desktop; anchored above the tab bar + player bar on phone), 3s auto-dismiss. Stacks multiple toasts vertically via `#toast-root` flex column. `aria-live="polite"` on `#toast-root` (Sprint 6, FE-4) so new toasts are announced without moving focus.

```
┌─────────────────────┐
│  Added to Melo      │
└─────────────────────┘
```

- Rendered by `renderToast(message, type)` in `components.js`. Appended to `#toast-root`, removed after 3s.
- `type: 'error'` applies `.toast--error` — red border and red text — used for failed API actions (delete, favorite toggle, playlist ops, reorder-resync, etc).

### Health Banner

Full-width fixed banner at the very top of the viewport (`.health-banner`, `--danger` background, white text). Shown on boot if `GET /health` is unreachable or reports non-`ok` status. Persists until the page is refreshed (no dismiss button).

```
┌──────────────────────────────────────────────────────┐
│      Cannot reach API. Is the server running?        │
└──────────────────────────────────────────────────────┘
```

### Playlist Card

```
┌─────────────────────────┐
│  Morning Mix          ✕ │
│  3 songs                │
└─────────────────────────┘
```

- Rendered by `renderPlaylistCard()` in `components.js`
- Whole card is clickable → navigates to playlist detail
- **Delete button position (fixed this session):** the `✕` icon button (`.icon-btn--danger`) is absolutely positioned top-right of the card (`.playlist-card { position: relative }`, button `position: absolute; top; right`) — previously fell to the bottom of the card via normal document flow. Opens the Confirm Dialog.

### Playlist Detail — Drag Reorder (Sprint 6, FE-2)

Each row (`.playlist-song-row`) wraps a position number, the song card, and a remove button:

```
┌──────────────────────────────────────────────────────┐
│ 1  [thumb]  Title                     03:32  ♡  ⋮   ✕│
└──────────────────────────────────────────────────────┘
```

- Native HTML5 drag-and-drop (`draggable="true"`, `dragstart`/`dragover`/`drop`/`dragend`), wired through the existing document-level event-delegation listeners
- Drop-onto-row inserts the dragged song *after* the target row's current index
- Optimistic reorder in the UI, `PATCH /playlists/{id}/songs/{song_id}` fired in the background; on failure, re-fetches the playlist to resync
- **Keyboard alternative** (Sprint 6, FE-4): rows are `tabindex="0"` and focusable; `ArrowUp`/`ArrowDown` call the same `reorderPlaylistSongOptimistic()` path drag uses, with focus restored to the moved row after re-render. `aria-label` states position/total ("Song Title, position 2 of 5"); an `sr-only` hint states the key binding. No-op at the list boundaries (top row + ArrowUp, bottom row + ArrowDown).
- Rows are plain focusable `<div>`s, not given `role="button"` or a listbox/option ARIA pattern — the row wraps other interactive elements (the song card itself, the remove button), so a nested interactive role on the wrapper would create ambiguity for screen readers
- Known cosmetic gap: the native drag-preview shows only the song thumbnail (browsers make `<img>` natively draggable), not the full row — reorder logic still works correctly via event-delegation bubbling; fix deferred to Sprint 7

---

## Motion

Minimal. Nothing decorative.

| Event                     | Animation                                       |
| ------------------------- | ----------------------------------------------- |
| Page load                 | Fade in `#page-content`, 150ms ease             |
| Modal open/close          | Opacity + scale(0.97→1), 120ms                  |
| Now Playing panel open    | Fade in, 120ms (shares `.modal`-style entrance) |
| Song card hover           | Background transition, 80ms                     |
| Status pulse (processing) | Dot opacity 0.4→1, 1s infinite                  |
| Toast notification        | Slide up + fade in, 200ms                       |
| Dropdown menu open        | Fade in, 80ms                                   |
| Loading skeleton          | Background shimmer, 1.5s infinite               |
| Add Song preview spinner  | Rotate 360°, 0.8s linear infinite               |

No bounces. No spring physics. No page transitions. Player bar title/channel swap instantly on song change with no transition — not animated, despite earlier plans.

---

## Interaction States

```css
/* Default */
background: var(--bg-surface);

/* Hover */
background: var(--bg-elevated);
transition: background 80ms ease;

/* Focus */
outline: 1px solid var(--accent);
outline-offset: 2px;

/* Disabled */
opacity: 0.4;
cursor: not-allowed;

/* Loading skeleton */
background: linear-gradient(90deg, var(--bg-surface), var(--bg-elevated), var(--bg-surface));
background-size: 200%;
animation: shimmer 1.5s infinite;

/* Range input progress fill (scrubber + volume, Player Bar + Now Playing panel) */
background: linear-gradient(to right,
  var(--accent) var(--progress, 0%),
  var(--bg-elevated) var(--progress, 0%));
```

`--progress` is a per-element CSS custom property, set from JS — range inputs can't reflect their own live `.value` in CSS alone.

---

## Pages

### Library `#/`

- Sticky filter bar: search input, status dropdown, sort dropdown
- Song list with "Load more" button (cursor pagination via `bookmark`)
- Empty state: centered "No songs yet." + [Add Song] button
- Auto-poll every 2s while any song `pending`/`processing`

### Favorites `#/favorites`

- Same song card list, no filters
- Empty state: "No favorites yet."

### Playlists `#/playlists`

- Grid of playlist cards (name, song count, created date), delete button top-right of each card
- [+ New Playlist] inline input top right

### Playlist Detail `#/playlists/:id`

- Ordered song list (numbered), drag-to-reorder (mouse) or Arrow Up/Down (keyboard) — see Drag Reorder above
- Remove song button per row

---

## Responsive

**As of Sprint 6, Melo is responsive across three tiers** — this reverses the earlier Sprint-4/early-Sprint-5 "desktop-first, 1280px minimum, no mobile layout" decision. See App Shell above for the full breakpoint table. Desktop behavior at >=1280px is otherwise unchanged from the original design.

---

## Accessibility

- All interactive elements keyboard-navigable
- Focus rings visible via `:focus-visible` + `--accent` outline
- `aria-label` on icon-only buttons
- Color not sole indicator of status (always paired with text)
- Manual focus trap on `.modal` and the Now Playing panel (shared `trapFocus()`)
- `Escape` priority chain: Now Playing panel → open dropdown → modal (only the topmost surface closes per press)
- `#toast-root` is `aria-live="polite"` — new toasts announced without moving focus
- Dropdown triggers carry `aria-haspopup`/`aria-expanded`; menu/items are native `<button>`s with no ARIA menu role (no keyboard model to back it — see `DECISIONS.md`)
- Playlist rows: keyboard reorder via Arrow Up/Down, with `aria-label` stating position/total and an `sr-only` hint for the binding
- Known gap (Sprint 6, FE-4): a full manual tab-order pass across all pages/breakpoints is still outstanding — needs an actual browser, not automatable via the smoke test suite

---

## Tech Stack

```
Vanilla HTML5
CSS3 (custom properties, grid, flexbox)
Vanilla JavaScript ES2020 (modules)
Native <audio> element
Web Audio API (AudioContext, waveform decoding — Sprint 6, FE-3)
<canvas> (waveform rendering — Sprint 6, FE-3)
nginx (static serving + API proxy)
```

No build step. No package manager. No framework. Files served directly by nginx.

---

## File Conventions

```
ui/
  index.html      # app shell, <link> fonts + favicon, <script type="module" src="app.js">
  style.css       # :root tokens + all component styles + animations + breakpoints
  api.js          # apiFetch() + all endpoint wrappers (export)
  player.js       # <audio> element, queue/shuffle/loop/volume state, waveform peaks,
                  #   subscribe() pub-sub for the Now Playing panel (export)
  components.js   # renderSongCard(), renderStatusPill(), renderPlaylistCard(), renderToast() (export)
  app.js          # hash router, page renderers, polling, event delegation,
                  #   modal markup (Add Song, Confirm Dialog) built inline here,
                  #   Now Playing panel markup + waveform draw, drag-reorder handlers
  assets/
    logo.png      # favicon + sidebar mark (Sprint 6, this session)
  nginx.conf
  Dockerfile
```

> Note: modal markup (Add Song flow, delete confirmations) is **not** a `renderModal()` export from `components.js` — it's built as inline HTML-string builders inside `app.js` (`buildStep1Html`, `buildStep1LoadingHtml`, `showStep2`, `confirmDeleteSong`, `confirmDeletePlaylist`). Now Playing panel markup follows the same inline-builder pattern (`buildNowPlayingHtml`).

---

## Admin Dashboard (out of scope for this spec)

Melo also ships a separate **Streamlit-based admin dashboard** (`admin/`) for observability — health overview, song status/re-queue, live logs (Loki), metrics (Prometheus), alerts (Grafana), and DB health (Postgres/Redis exporters). It uses Streamlit's own theming rather than the tokens on this page and is not part of the main Melo UI. See `PRD.md` / `Sprint-5.md` for its design and page breakdown.

---

## What This Is Not

- No dark/light toggle (dark only)
- No animations beyond the table above
- No framework, bundler, or package manager
- No color themes
- No frontend automated tests (Sprint 4 decision, still holds — no component framework means no test surface; covered by manual smoke checklist instead)
- No onboarding flow (self-hosted, you know what it is)
- No TypeScript (plain JS with JSDoc comments where helpful)
- No waveform click-to-seek (the separate scrubber handles seeking instead) — deliberately out of scope, not a gap
- No bulk/multi-select playlist reorder (Sprint 7+ candidate)
