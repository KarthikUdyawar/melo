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

Single accent color. No gradients. No decorative illustrations.
Thumbnails from YouTube are the only "color" in the UI.

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

**App shell:** CSS Grid. Fixed sidebar (220px) + scrollable main + fixed player bar (72px).

```
┌──────────────────────────────────────────┐
│  sidebar (220px)  │  main content area   │
│                   │                      │
│  [logo]           │  [page content]      │
│                   │                      │
│  nav links        │                      │
│                   │                      │
├───────────────────┴──────────────────────┤
│  player bar (72px, full width)           │
└──────────────────────────────────────────┘
```

```css
/* Shell layout */
body {
  display: grid;
  grid-template-columns: 220px 1fr;
  grid-template-rows: 1fr 72px;
  height: 100vh;
}

.sidebar    { grid-row: 1; grid-column: 1; }
.main       { grid-row: 1; grid-column: 2; overflow-y: auto; }
.player-bar { grid-row: 2; grid-column: 1 / -1; }
```

---

## Components

### Song Card

Horizontal layout. Thumbnail left (48×48, rounded-sm), title + metadata right, actions far right.

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

### Overflow Menu (Song Card `⋮`)

Dropdown anchored to the song card's `⋮` icon button (`.dropdown` / `.dropdown__menu`), opened/closed via click and closed automatically on outside click.

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

### Player Bar

Fixed bottom. Full width. Three zones:

```
┌─────────────────────────────────────────────────────────┐
│  [thumb] Title          ◀  ▶  ━━━━━●━━━━  00:42 / 03:32 │
│          Channel                                         │
└─────────────────────────────────────────────────────────┘
```

- Single `<audio>` element in DOM — persists across page navigation
- Progress bar: `<input type="range">` styled with accent color thumb
- `player.js` syncs scrubber via `audio.ontimeupdate`
- Hidden (`player-bar--empty` class) when no song loaded
- Title/channel swap instantly on song change — no transition applied (see Motion table)

### Add Song Modal

Full-screen overlay. Two-step flow managed in `app.js`. Built via inline HTML-string builders (`buildStep1Html`, `buildStep1LoadingHtml`, `showStep2`) — there is no `renderModal()` helper in `components.js`.

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
- `Esc` closes modal (keydown listener in `app.js`)

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

Rendered by `renderStatusPill(status)` in `components.js`. Returns empty string for `done`.

### Sidebar Nav

```
  melo

  Library
  Favorites
  Playlists

  [+ Add Song]   ← accent button, bottom of sidebar
```

Plain text nav links — no bullet/icon glyphs in the markup. Active link detected via `window.location.hash`. Active: left border 2px `--accent`, text `--text-primary`. Inactive: `--text-secondary`.

### Toast

Slides up from just above the player bar (`bottom: 88px`, not the viewport edge), 3s auto-dismiss. Stacks multiple toasts vertically via `#toast-root` flex column.

```
┌─────────────────────┐
│  Added to Melo      │
└─────────────────────┘
```

- Rendered by `renderToast(message, type)` in `components.js`. Appended to `#toast-root`, removed after 3s.
- `type: 'error'` applies `.toast--error` — red border and red text — used for failed API actions (delete, favorite toggle, playlist ops, etc).

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
│  Morning Mix        ✕  │
│  3 songs                │
└─────────────────────────┘
```

- Rendered by `renderPlaylistCard()` in `components.js`
- Whole card is clickable → navigates to playlist detail
- Inline `✕` delete icon button (`.icon-btn--danger`) in the corner opens the Confirm Dialog

---

## Motion

Minimal. Nothing decorative.

| Event                     | Animation                           |
| ------------------------- | ----------------------------------- |
| Page load                 | Fade in `#page-content`, 150ms ease |
| Modal open/close          | Opacity + scale(0.97→1), 120ms      |
| Song card hover           | Background transition, 80ms         |
| Status pulse (processing) | Dot opacity 0.4→1, 1s infinite      |
| Toast notification        | Slide up + fade in, 200ms           |
| Dropdown menu open        | Fade in, 80ms                       |
| Loading skeleton          | Background shimmer, 1.5s infinite   |
| Add Song preview spinner  | Rotate 360°, 0.8s linear infinite   |

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
```

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

- Grid of playlist cards (name, song count, created date)
- [+ New Playlist] inline input top right

### Playlist Detail `#/playlists/:id`

- Ordered song list (numbered)
- Remove song button per row

---

## Responsive

Self-hosted personal tool — **desktop-first**. Minimum supported: 1280px wide.
No mobile layout for v1.

---

## Accessibility

- All interactive elements keyboard-navigable
- Focus rings visible via `:focus-visible` + `--accent` outline
- `aria-label` on icon-only buttons
- Color not sole indicator of status (always paired with text)

---

## Tech Stack

```
Vanilla HTML5
CSS3 (custom properties, grid, flexbox)
Vanilla JavaScript ES2020 (modules)
Native <audio> element
nginx (static serving + API proxy)
```

No build step. No package manager. No framework. Files served directly by nginx.

---

## File Conventions

```
ui/
  index.html      # app shell, <link> fonts, <script type="module" src="app.js">
  style.css       # :root tokens + all component styles + animations
  api.js          # apiFetch() + all endpoint wrappers (export)
  player.js       # loadSong(), play(), pause(), scrubber sync (export)
  components.js   # renderSongCard(), renderStatusPill(), renderPlaylistCard(), renderToast() (export)
  app.js          # hash router, page renderers, polling, event delegation,
                  #   modal markup (Add Song, Confirm Dialog) built inline here
  nginx.conf
  Dockerfile
```

> Note: modal markup (Add Song flow, delete confirmations) is **not** a `renderModal()` export from `components.js` — it's built as inline HTML-string builders inside `app.js` (`buildStep1Html`, `buildStep1LoadingHtml`, `showStep2`, `confirmDeleteSong`, `confirmDeletePlaylist`).

---

## Admin Dashboard (out of scope for this spec)

Melo also ships a separate **Streamlit-based admin dashboard** (`admin/`) for observability — health overview, song status/re-queue, live logs (Loki), metrics (Prometheus), alerts (Grafana), and DB health (Postgres/Redis exporters). It uses Streamlit's own theming rather than the tokens on this page and is not part of the main Melo UI. See `PRD.md` / `Sprint-5.md` for its design and page breakdown.

---

## What This Is Not

- No dark/light toggle (dark only)
- No animations beyond the table above
- No framework, bundler, or package manager
- No color themes
- No responsive/mobile layout
- No onboarding flow (self-hosted, you know what it is)
- No TypeScript (plain JS with JSDoc comments where helpful)
