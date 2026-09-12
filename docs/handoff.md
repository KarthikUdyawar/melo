# Handoff — Sprint 7: FE7-2 Components + FE7-5 Routes (in progress)

## Context

Repo: `KarthikUdyawar/melo`. Branch: `feature/sprint7-nextjs-frontend-rewrite`. Solo project. **This session's scope: FE7-2 (port components) fully, FE7-5 (real routes) partially, both TDD'd file-by-file with real `pnpm test`/`lint`/`build` runs after each change.** Previous handoff covered getting the scaffold to actually build/test for the first time (resolved, all green as of last session's close). Full ticket scope/locked decisions still live in `docs/PRD.md`/`docs/DECISIONS.md` — not duplicated here.

**Note:** this doc replaces the "first real build/test run" handoff — that session's scope is done and folded into `TODO.md`/`DECISIONS.md`. The yt-dlp 403 hotfix (unsprinted, Sep 2026) is still open and independent of this sprint — see `docs/DECISIONS.md`'s "Hotfix" section and `docs/TODO.md`'s Hotfix block. Don't lose track of it.

Conventions in effect: **caveman ultra**, **clean-code**, **tdd**, **ponytail**. Terse responses, minimal diffs, git-diff format by default.

## What happened, in order

1. **FE7-2 component port** — `StatusPill`, `SongCard`, `SongCardMenu` (dropdown, no ARIA menu role per Post-Sprint-6 fix), `PlaylistCard`, `ToastProvider`/`useToast` (replaces the old imperative `renderToast()`), generic `<Modal>` shell (focus-trap + Escape + overlay-click-close), `<ConfirmDialog>` (re-scoped here from a misread of PRD's table — only `<AddSongModal>` is FE7-8). Helpers `formatDuration`/`trapFocus` ported as pure functions, each TDD'd (red confirmed via jsdom's `offsetParent` gotcha below).
2. **`trapFocus()` jsdom gotcha** — first test run failed both focus-wrap cases (`toHaveBeenCalled` 0 times). Root cause: jsdom has no layout engine, so `offsetParent` is always `null` regardless of real visibility — the ported filter (`el.offsetParent !== null`) silently emptied the focusables list every time. Dropped that filter; noted in code that real hidden-element checks should use `.hidden`/computed `display` instead, not `offsetParent`.
3. **Lint/build cleanup, several rounds** (each only surfaced by actually running the command, not guessable from a diff):
   - `SongCard`'s `<img>` → `next/image`'s `<Image unoptimized>`, silencing `@next/next/no-img-element`. `unoptimized` kept explicit per-element (not just relying on `next.config.mjs`'s global setting).
   - `jest.config.ts`'s anonymous default export → named async function, silencing `import/no-anonymous-default-export`.
   - `focus-trap.ts` TS build error (`'last' is possibly 'undefined'`) — `noUncheckedIndexedAccess` flagged array-index access even though the length check above guarantees both indices exist; non-null assertions added.
   - `msw-polyfills.ts` TS build error (`Definitions ... conflict with those in another file`) — `next build`'s typecheck was pulling this Jest-only file into the production typecheck via `tsconfig.json`'s blanket `**/*.ts` include, where its `require()`-based global polyfills collided with `lib.dom`'s own declarations. Fixed by excluding `src/test/**/*` in `tsconfig.json` (Jest doesn't consult this include/exclude list, so `pnpm test` unaffected).
   - Stray `/* eslint-disable @typescript-eslint/no-var-requires */` in `msw-polyfills.ts` → hard error, not a warning: the referenced rule was never registered (`next/core-web-vitals` doesn't pull in `@typescript-eslint`'s plugin), so ESLint treats the disable comment itself as invalid. Removed — same root cause as Sprint 7's earlier `no-unused-vars` rule drop.
   - `pnpm lint` was walking into `out/`'s compiled build output and flagging React internals inside minified vendor bundles. Added `.eslintignore` (`out/`, `.next/`, `node_modules/`).
4. **FE7-5 page wiring, started** — `<Nav>` (sidebar + tab bar + phone FAB, `usePathname()`-based active-link detection replacing the old hash router's `highlightNavLink()`), wired into `layout.tsx` alongside `ToastProvider` and a static player-bar placeholder (real audio wiring is FE7-4/FE7-6, not this ticket). Pages written: `/` (Library — search/status/sort filters, 2s poll while any song pending/processing, cursor pagination via `hasMorePages()`), `/favorites`, `/playlists` (grid + inline create), `/playlists/[id]` (read-only ordered list — drag-reorder is FE7-7). Two new pure-function helpers TDD'd: `parsePlaylistId()` (reads the real playlist id from `window.location.pathname`, since the static-export shell can't know it at build time) and `hasMorePages()` (ported bookmark/short-page pagination-end logic from the old `app.js`).
5. **`pnpm build` currently broken** — `/playlists/[id]/page.tsx` combines `"use client"` with an exported `generateStaticParams()`. Next 14 disallows this outright (`generateStaticParams` must live in a Server Component). Not fixed yet — see Still Open.

## Still open — next session should start here

- **`pnpm build` is red right now — fix this first.** `/playlists/[id]/page.tsx`'s `"use client"` + `generateStaticParams()` combo is invalid. Plan: split into a thin Server Component `page.tsx` that only exports `generateStaticParams()` (returning `[{ id: "_" }]`), delegating render to a separate `"use client"` child component that does the `window.location.pathname` parsing + `api.getPlaylist()` fetch + song-list render. Not started.
- **FE7-5 has no page-level tests yet.** `ConfirmDialog`, `parsePlaylistId`, `hasMorePages` are unit-tested; the pages themselves (`page.tsx` files) aren't — would need msw handlers per page. Flagged for FE7-9, not blocking FE7-5's remaining work.
- **`src/lib/api.ts`'s exact export shapes were inferred, not re-verified against the real file** while writing FE7-5's pages (`listSongs`, `submitSong` param shape, etc.) — assumed consistent with FE7-3's original diff. Worth a quick sanity pass next session since `pnpm build`'s typecheck would have caught real mismatches, but confirm once the `generateStaticParams` blocker is cleared and a full `pnpm build` runs clean end-to-end.
- **Nav's Add Song buttons (sidebar + FAB) are disabled stubs.** FE7-8 owns wiring them to `<AddSongModal>`.
- **Player bar in `layout.tsx` is a static empty-state placeholder**, no audio element, no state. FE7-4 (`PlayerProvider`) + FE7-6 (Player Bar/Now Playing panel) own the real version.
- **`/playlists/[id]` page is read-only** (no drag-reorder) — that's FE7-7's scope, deliberately not touched here.
- **`ui/src/app/globals.css` was replaced wholesale this session** (full-file swap, not a diff) with the ported design tokens + component styles from the old vanilla `style.css`, plus FE7-1's 3 hand-kept CSS-only exceptions (range-input thumbs, `--progress` gradient, `@keyframes`). Confirm the applied file matches what was intended — it was given as a full block since the assistant couldn't verify FE7-1's exact prior bytes to diff against safely.
- **`ui/public/assets/logo.png` needs to exist** — `Nav.tsx` references `/assets/logo.png` (Next serves `public/` at root). Not copied automatically; copy the old `ui/assets/logo.png` into `ui/public/assets/logo.png`.
- **Everything from the previous handoff (scaffold build/test run) is still resolved and unaffected** — `docker-compose.yml`/`INFRA.md`'s port-table update (3000→4000/4443), `Makefile`'s stale echoed URL, `FRONTEND_SETUP.md`'s Common Gotchas entries, the local-dev API proxy decision, and old `ui/*` vanilla file deletion are all still outstanding from before, unrelated to this session's work. See prior `TODO.md` entries.
- **FE7-4 (`PlayerProvider`)** is still fully unstarted and still unblocked (`PRD.md`: only depends on FE7-0). Plan unchanged: pure-logic tests first (Fisher–Yates-keeps-current, `findNextPlayableIndex`, shuffle restore, loop-mode cycle, peak-downsampling math), zero DOM/JSX, same TDD pattern already proven out on FE7-2/FE7-3/FE7-5's helpers.

## Files touched this session (as diffs, not yet applied to a real branch)

- `ui/src/lib/format.ts`, `format.test.ts` — new, ported `formatDuration`
- `ui/src/lib/focus-trap.ts`, `focus-trap.test.ts` — new, ported `trapFocus`, jsdom `offsetParent` fix
- `ui/src/lib/playlist-path.ts`, `playlist-path.test.ts` — new, `parsePlaylistId()`
- `ui/src/lib/pagination.ts`, `pagination.test.ts` — new, `hasMorePages()`
- `ui/src/components/StatusPill.tsx` + test — new
- `ui/src/components/SongCard.tsx` + test — new, thumbnail uses `next/image`
- `ui/src/components/SongCardMenu.tsx` — new
- `ui/src/components/PlaylistCard.tsx` + test — new
- `ui/src/components/Toast.tsx` + test — new (`ToastProvider`/`useToast`)
- `ui/src/components/Modal.tsx` + test — new
- `ui/src/components/ConfirmDialog.tsx` + test — new
- `ui/src/components/Nav.tsx` — new
- `ui/src/app/layout.tsx` — wired `ToastProvider`, `Nav`, placeholder player bar
- `ui/src/app/page.tsx` — replaced placeholder with real Library page
- `ui/src/app/favorites/page.tsx`, `ui/src/app/playlists/page.tsx`, `ui/src/app/playlists/[id]/page.tsx` — new (last one currently build-broken, see Still Open)
- `ui/src/app/globals.css` — full-file replace (see Still Open note)
- `ui/tsconfig.json` — excluded `src/test/**/*`
- `ui/jest.config.ts` — named the async export function
- `ui/src/test/msw-polyfills.ts` — removed stray unregistered-rule disable comment
- `ui/.eslintignore` — new (`out/`, `.next/`, `node_modules/`)
- `docs/TODO.md`, `docs/DECISIONS.md`, `docs/handoff.md` — this session's log

## For the next session

- First priority: fix the `generateStaticParams`/`"use client"` build break on `/playlists/[id]/page.tsx` — nothing else in FE7-5 can be called done until `pnpm build` is green again.
- Then: finish FE7-5 (page-level tests, confirm `lib/api.ts` shapes) or move to FE7-4 (`PlayerProvider`) — both are now realistic next steps.
- `INFRA.md` port-table diff for the real `4000`/`4443` ports — still outstanding from before, small/standalone.
- `FRONTEND_SETUP.md` Common Gotchas additions — now has two more sessions' worth of fixes to log (msw/Jest six-fix list, plus this session's lint/typecheck/jsdom fixes). Worth doing in one pass before it goes stale.
- Decide the local-dev API proxy question (still open, see prior handoff) — blocks comfortable `pnpm dev` iteration on later tickets.
- Recommended skills for continuation: `caveman` (ultra), `clean-code`, `tdd`, `ponytail` — all standing preferences already in memory, all followed this session.
- Reminder: the yt-dlp 403 hotfix (separate, unsprinted work) is still unresolved — see `docs/TODO.md`'s Hotfix block. Not blocking Sprint 7, but don't forget it exists.
