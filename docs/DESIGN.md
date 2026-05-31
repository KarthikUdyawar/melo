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
- Rendered as HTML string by `renderSongCard()` in `components.js`

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

### Add Song Modal

Full-screen overlay. Two-step flow managed in `app.js`.

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
  ◉ melo

  ▸ Library
  ▸ Favorites
  ▸ Playlists

  [+ Add Song]   ← accent button, bottom of sidebar
```

Active link detected via `window.location.hash`. Active: left border 2px `--accent`, text `--text-primary`. Inactive: `--text-secondary`.

### Toast

Slide up from bottom, 3s auto-dismiss.

```
┌─────────────────────┐
│  ✓  Added to Melo   │
└─────────────────────┘
```

Rendered by `renderToast(message, type)` in `components.js`. Appended to `<body>`, removed after 3s.

---

## Motion

Minimal. Nothing decorative.

| Event                     | Animation                           |
| ------------------------- | ----------------------------------- |
| Page load                 | Fade in `#page-content`, 150ms ease |
| Modal open/close          | Opacity + scale(0.97→1), 120ms      |
| Song card hover           | Background transition, 80ms         |
| Status pulse (processing) | Dot opacity 0.4→1, 1s infinite      |
| Player bar song change    | Title fade out/in, 100ms            |
| Toast notification        | Slide up from bottom, 200ms         |

No bounces. No spring physics. No page transitions.

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
  components.js   # renderSongCard(), renderStatusPill(), renderModal(), renderToast() (export)
  app.js          # hash router, page renderers, polling, event delegation
  nginx.conf
  Dockerfile
```

---

## What This Is Not

- No dark/light toggle (dark only)
- No animations beyond the table above
- No framework, bundler, or package manager
- No color themes
- No responsive/mobile layout
- No onboarding flow (self-hosted, you know what it is)
- No TypeScript (plain JS with JSDoc comments where helpful)
