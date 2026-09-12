# Melo — Sprint 7: Frontend Rewrite (Next.js/TS/Tailwind)

**Owner:** Karthik | **Repo:** `melo` | **Sprint:** 7 | **Timeline:** no fixed deadline (solo)
**Reverses:** Sprint 4's "vanilla JS, no build step, no framework" call and Sprint 4/6's "no frontend tests" call (`DECISIONS.md`).

---

## Problem

`ui/` (vanilla HTML/JS/CSS) works but every FE-3/FE-4/CodeRabbit bug this project has hit (stale doc-level listeners, ID-scoped CSS missing a second surface, races between `change`/`mouseup`/`touchend`, a shuffle mutating queue in place) is a symptom of hand-rolled DOM state management with no component boundaries and zero test surface. The app has outgrown `innerHTML` + event delegation.

---

## Goal

> *Same UI, same behavior, real components, real types, real tests.*

No visual or UX change. `DESIGN.md`/`USER-FLOW.md` stay the source of truth for what the app looks like and does — this sprint changes *how it's built*, not what it is.

---

## Scope

### ✅ In

| Ticket | Feature                                                                                              |
| ------ | ---------------------------------------------------------------------------------------------------- |
| FE7-0  | Scaffold: Next 14 App Router (static export) + TS + pnpm + ESLint + Tailwind + Jest/RTL/msw          |
| FE7-1  | Design tokens → Tailwind theme + minimal `globals.css` for what Tailwind can't express               |
| FE7-2  | Port all components 1:1 (SongCard, StatusPill, PlaylistCard, Toast, Modal, dropdown, confirm dialog) |
| FE7-3  | Typed API client (`lib/api.ts`), ported from `api.js`                                                |
| FE7-4  | `PlayerProvider` context — queue/shuffle/loop/volume/waveform, ported from `player.js`               |
| FE7-5  | Real routes: `/`, `/favorites`, `/playlists`, `/playlists/[id]` (client-resolved shell, see below)   |
| FE7-6  | Player Bar + Now Playing panel, ported from `app.js`'s inline builders                               |
| FE7-7  | Drag-reorder (native HTML5 DnD) + keyboard reorder, ported                                           |
| FE7-8  | Add Song modal 2-step flow, ported                                                                   |
| FE7-9  | Jest + RTL unit/component tests, msw for `lib/api.ts` — coverage ≥ 80% (new FE test surface)         |
| FE7-10 | HTTPS: self-signed cert baked into `ui` nginx image, 80→443 redirect                                 |
| FE7-11 | Docker: static export served by nginx, same topology as Sprint 4–6                                   |

### ❌ Out

- Any visual/UX change — this is a stack swap, not a redesign
- SSR/`next start` — static export only, per the locked HTTPS/routing decisions below
- New features beyond what Sprint 4–6 already shipped
- Node runtime in the prod container

---

## Locked Decisions (this sprint's brainstorm, before scoping)

| Decision                                                         | Reason                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Real routes (`/playlists/[id]`), not hash routing                | Karthik's call — idiomatic Next, cleaner URLs                                                                                                                                                                                                                                                                                                                                                                                                   |
| Static export (`output: 'export'`) kept, not `next start`        | No new Node runtime container; nginx keeps serving static files, same as Sprint 4–6                                                                                                                                                                                                                                                                                                                                                             |
| Dynamic playlist route resolved client-side                      | Static export needs `generateStaticParams` at build time; playlist IDs are runtime DB data, unknowable at build. `generateStaticParams` emits one placeholder shell (`/playlists/_/`); nginx rewrites any real `/playlists/<uuid>/` request to that shell; the page reads the real ID from `window.location.pathname` client-side, not from Next's `params`. Address bar shows the real URL throughout — visually identical to true SSR routing |
| Tailwind, hybrid with a small `globals.css`                      | Design tokens map cleanly to Tailwind theme; `input[type=range]` thumb pseudo-elements, the `--progress` gradient-fill var, and `@keyframes` don't have a clean Tailwind-utility equivalent — those three stay hand-written CSS                                                                                                                                                                                                                 |
| msw for `lib/api.ts` tests, not manual `jest.fn()` mocks         | Karthik's call — request-level mocking closer to real fetch behavior, worth the one extra devDep                                                                                                                                                                                                                                                                                                                                                |
| HTTPS: self-signed cert baked into `ui`'s nginx image            | Solo self-hosted box on a home network, not a public domain — certbot/Let's Encrypt needs a real domain and renewal automation that doesn't apply here; a separate reverse-proxy container was considered and rejected as unnecessary extra infra for this scope                                                                                                                                                                                |
| `PlayerProvider` context mounted once in root `layout.tsx`       | Root layout persists across route navigation in Next App Router — same "audio element survives page change" guarantee the vanilla `player.js` module-singleton had                                                                                                                                                                                                                                                                              |
| Waveform/DnD get logic-only unit tests, not full jsdom DOM tests | `AudioContext`/`<canvas>` decode and native HTML5 `dataTransfer` are unsupported/flaky in jsdom; peak-downsampling math and reorder-index math are pure functions and get tested directly instead                                                                                                                                                                                                                                               |

---

## FE7-0 — Scaffold

Next 14 App Router, TypeScript, pnpm, ESLint (`next/core-web-vitals`), Tailwind, Jest + `@testing-library/react` + msw. `output: 'export'`, `images.unoptimized: true` (static export can't use the Next image optimizer — same reasoning as the pinned-format-selector/no-JS-runtime trades elsewhere in this project: accept a constraint to avoid a heavier dependency).

Old `ui/` (vanilla files) removed wholesale, replaced by the Next project at the same path.

---

## FE7-1 — Design Tokens → Tailwind

All `DESIGN.md` CSS custom properties (`--bg-base`, `--accent`, `--font-display`, spacing scale, radii) become `tailwind.config.ts` `theme.extend` entries — `bg-surface`, `text-primary`, `font-display`, `rounded-md`, etc. become real utility classes. No design values change.

`globals.css` keeps only what Tailwind can't do cleanly:
- `input[type=range]::-webkit-slider-thumb` / `::-moz-range-thumb` (scrubber + volume slider thumbs)
- `--progress` CSS custom property + its `linear-gradient` fill rule (JS sets it per-tick, same as before)
- `@keyframes` (`fade-in`, `modal-in`, `dot-pulse`, `shimmer`, `spin`, `toast-in`)
- `.sr-only`

---

## FE7-2 — Components

1:1 port of `components.js`'s pure render functions into React components, same markup/classes/behavior:

| Old (function)                             | New (component)                                                                                                        |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `renderStatusPill`                         | `<StatusPill status />`                                                                                                |
| `renderSongCard`                           | `<SongCard song isActive playlistNames />`                                                                             |
| `renderPlaylistCard`                       | `<PlaylistCard playlist />`                                                                                            |
| `renderToast` (imperative DOM append)      | `<ToastProvider>` context + `<Toast />`, `useToast().show(message, type)` replaces the imperative `renderToast()` call |
| inline modal builders in `app.js`          | `<AddSongModal>`, `<ConfirmDialog>`                                                                                    |
| inline dropdown markup in `renderSongCard` | `<SongCardMenu>` (still plain buttons, no `role="menu"` — matches the post-Sprint-6 CodeRabbit fix)                    |

---

## FE7-3 — API Client

`lib/api.ts` — same envelope-unwrap/error-shape logic as `apiFetch()`, typed against `API_DOC.md`'s Song/Playlist/envelope shapes. Same function set (`previewSong`, `submitSong`, `listSongs`, `getSong`, `deleteSong`, favorites, playlists, `reorderSongInPlaylist`, `checkHealth`).

---

## FE7-4 — Player

`PlayerProvider` (React context) replaces the module-scope `<audio>` singleton in `player.js`. Same state shape: `queue`, `originalQueue`, `queueIndex`, `shuffle` (session-only), `loopMode` (persisted `localStorage['melo:loop']`), `volume` (persisted, debounced 300ms — same fix as the Post-Sprint-6 CodeRabbit entry). Same `subscribe()`-shaped API surface internally, but consumed via `usePlayer()` hook instead of manual `subscribe()`/DOM query calls.

Same queue semantics: `setQueueAndPlay`, Fisher–Yates shuffle keeping current song in place, `findNextPlayableIndex` skip-non-done logic, `prev()` >3s-restart convention, `onended` loop handling — all ported as-is, not re-decided.

Waveform: `getPeaks(songId, signal)` ports as-is (in-memory `Map` cache, `AbortController` per panel-open/song-switch, same as the Post-Sprint-6 fix).

---

## FE7-5 — Routing

| Old hash route    | New path                                                        |
| ----------------- | --------------------------------------------------------------- |
| `#/`              | `/`                                                             |
| `#/favorites`     | `/favorites`                                                    |
| `#/playlists`     | `/playlists`                                                    |
| `#/playlists/:id` | `/playlists/[id]` (client-resolved shell, see Locked Decisions) |

nginx rewrite for the dynamic segment:
```nginx
location ~ ^/playlists/[^/]+/?$ {
    try_files $uri /playlists/_/index.html;
}
```

---

## FE7-6 — Player Bar + Now Playing Panel

Ported from `app.js`'s inline HTML builders (`buildNowPlayingHtml`, the player-bar markup in `index.html`) into `<PlayerBar>` and `<NowPlayingPanel>` components, reading from `usePlayer()`. Same feature set: scrubber with `--progress` fill, shuffle/loop/volume controls, `role="dialog"`/`aria-modal`/focus-trap/reopen-guard on the panel (all Post-Sprint-6 fixes carried forward, not re-litigated).

---

## FE7-7 — Drag-Reorder

Native HTML5 DnD ported as-is (`draggable`, `dragstart`/`dragover`/`drop`/`dragend` handlers on `<PlaylistSongRow>`). Same "insert after target" semantics (Karthik-confirmed, Sprint 6). Keyboard alt (Arrow Up/Down) ported unchanged.

---

## FE7-8 — Add Song Modal

Same 2-step flow (`buildStep1Html`/loading/`showStep2` → `<AddSongModal>` internal step state), same inline-error-on-422/502 behavior, same spinner.

---

## FE7-9 — Tests

| Layer                  | Tool                                              | Coverage                                                                                                                                           |
| ---------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lib/api.ts`           | Jest + msw                                        | Every endpoint wrapper, envelope unwrap, error-shape mapping                                                                                       |
| `PlayerProvider` logic | Jest (pure functions)                             | Fisher–Yates-keeps-current, `findNextPlayableIndex`, shuffle restore, loop-mode cycle, peak downsampling math                                      |
| Components             | RTL                                               | SongCard render states (pending/processing/done/failed), StatusPill, Toast auto-dismiss, Modal open/close/focus-trap                               |
| Drag-reorder logic     | Jest (pure function)                              | "insert after target" index math, tested independent of jsdom DnD (see Locked Decisions)                                                           |
| Waveform decode        | Not tested at the `AudioContext`/`<canvas>` layer | jsdom doesn't implement Web Audio/canvas rendering meaningfully — same gap Sprint 6 had for manual smoke, now explicit instead of silently skipped |

Coverage target: ≥ 80% on `ui/`, brand new metric — Sprint 4/6 had 0% FE coverage by explicit decision, reversed this sprint.

---

## FE7-10 — HTTPS

Self-signed cert generated at image build time (`openssl req -x509 -nodes ...`), baked into the `ui` nginx image. nginx listens on 443 with the cert, 80 redirects to 443. Browser will show a self-signed warning on first visit — expected and accepted for a personal LAN box, not a public-facing service.

---

## FE7-11 — Docker

`ui/Dockerfile` becomes multi-stage: `pnpm install` + `pnpm build` (produces `out/`) in a build stage, then `COPY --from=build /app/out /usr/share/nginx/html` into the same `nginx:alpine` runtime stage as before. Topology unchanged from `INFRA.md` — no new container, no new port beyond 443.

---

## Ticket Breakdown & Order

| Ticket | Depends on   | Notes                                                                  |
| ------ | ------------ | ---------------------------------------------------------------------- |
| FE7-0  | —            | Foundation                                                             |
| FE7-1  | FE7-0        | Tokens before any component needs classes                              |
| FE7-2  | FE7-1        | Components need tokens to style against                                |
| FE7-3  | FE7-0        | Independent of UI work, can parallelize                                |
| FE7-4  | FE7-0        | Independent of UI work, can parallelize                                |
| FE7-5  | FE7-2, FE7-3 | Pages need components + API client                                     |
| FE7-6  | FE7-4, FE7-5 | Player Bar needs `PlayerProvider` + a page to sit in                   |
| FE7-7  | FE7-5        | Playlist Detail page must exist first                                  |
| FE7-8  | FE7-3, FE7-2 | Modal needs API client + Modal component shell                         |
| FE7-9  | FE7-2–FE7-8  | Tests follow implementation, TDD red-green per component as it's built |
| FE7-10 | FE7-11       | Cert bakes into the same image FE7-11 builds                           |
| FE7-11 | FE7-0        | Can be scaffolded early, finalized once `out/` exists to copy          |

---

## Open Questions — resolved

- Routing → real routes, client-resolved dynamic segment (Karthik's call, see Locked Decisions)
- Test mocking → msw (Karthik's call)
- HTTPS → self-signed baked into nginx image (Karthik's call)
- Static export vs `next start` → static export kept, to preserve no-new-container topology; flagged as the one open technical trade against "real routes" — proceeding on this default unless overridden
