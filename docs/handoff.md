# Handoff — Melo: Post-Sprint 6 CodeRabbit review pass (session 2)

## Context

Continuation of the post-Sprint 6 CodeRabbit review-fix batch (see prior
handoff `docs/handoff.md` for session 1 — playlist position compaction,
shuffle originalQueue, playSongById fallback, npCommitSeekHandler cleanup,
npPeaks clear-on-close, dead CSS rule). This session worked through the
remaining findings, verifying each against actual code before changing
anything, per Karthik's standing rule (`/caveman /ponytail /clean-code /tdd`).

## What changed this session

All changes are diffs already shown in-conversation; apply/reconcile against
your real repo (Claude has no direct repo access — outputs go to
`/mnt/user-data/outputs/`, Karthik copies by hand).

1. **`app/api/playlists.py`** — reorder endpoint had no row lock before
   reading membership/count, despite `API_DOC.md` claiming no race window.
   Added `_lock_playlist_songs()` (`SELECT ... FOR UPDATE`), called before
   `_get_membership_or_404`/song_count read, same transaction as the
   sentinel-shift. `docs/API_DOC.md` corrected to describe actual
   locking/contention behavior instead of the false no-race claim.
   - A concurrency integration test was attempted (two threads, two
     sessions off the same engine) and then **removed**: the integration
     `db_session` fixture (savepoint-rollback pattern, see
     `tests/integration/conftest.py`) means separate connections can't see
     each other's uncommitted rows, so real cross-connection lock
     contention isn't observable against it. Backlogged, not blocking —
     see `docs/TODO.md`.
2. **`tests/smoke_test.sh`**
   - S8: 502 handling now gates the "DB/MinIO volume drift" diagnosis on
     whether the song actually hit the dedup path (`DEDUP_HIT`, derived
     from S7's existing `ELAPSED <= 5` signal) instead of asserting it
     unconditionally. Non-dedup 502s now point at presigning/streaming/
     FFmpeg failure instead. The destructive `make down-v` recovery
     suggestion now explicitly warns about data loss and points at
     `make backup` first.
   - S17: the "unknown membership" reorder check was actually testing an
     unknown *song ID* (all-zero UUID -> `_get_song_or_404`), not the
     membership path. Added a real song (song D, created + polled to
     `done`, not added to the playlist) to actually exercise
     `_get_membership_or_404`; deleted immediately after the assertion.
3. **`tests/smoke_ui.sh`** — the FE-2 reorder section had one comment
   describing two unrelated checks (unknown-membership 404 vs
   out-of-range 422). Split into two comments, each scoped correctly.
4. **`ui/components.js`** — `aria-haspopup`/`aria-expanded` were on the
   `.song-card` (`role="listitem"`) wrapper instead of the
   `[data-action="open-menu"]` trigger button. Moved to the button.
   Cross-checked `ui/app.js`'s three `aria-expanded` sync sites (toggle
   click, outside-click, `closeOpenDropdown()`) — all three already
   targeted `[data-action="open-menu"]` correctly, so no knock-on fix was
   needed there.
5. **Docs** (`CHANGELOG.md`, `docs/PRD.md`, `docs/DECISIONS.md`):
   - `CHANGELOG.md`: "sentinel-position swap" -> "sentinel-position shift"
     (matches the actual shift-of-intermediate-rows mechanism and the
     existing "shift-not-swap" test).
   - `docs/PRD.md`: FE-2 behavior/status table rewritten to describe the
     sentinel-shift (both directions), dropped stale
     `IntegrityError`-retry/`409` language; FE-5's "`TODO.md` currently
     empty" changed to past tense; `smoke-ui.sh` -> `tests/smoke_ui.sh`;
     FE-3 dependency table corrected ("player bar" -> "Now Playing panel").
   - `docs/DECISIONS.md`: fixed a self-contradiction where the playlist
     keyboard-reorder row said "logged, not fixed this ticket" while the
     very next row (and actual `app.js` code —
     `handlePlaylistRowKeydown`/`reorderPlaylistSongOptimistic`) shows it
     was fixed same-sprint.

`docs/TODO.md` and `docs/DECISIONS.md` diffs for all of the above are in
this conversation's transcript — apply them to close out the Post-Sprint 6
CodeRabbit section.

## Still open (unchanged from before this session)

From `docs/TODO.md` / `docs/ROADMAP.md`:

- Manual tab-order pass across all pages/breakpoints — needs an actual
  browser, not automatable.
- Manual frontend smoke checklist (responsive, player controls, drag-drop,
  waveform, focus trap) — same, browser-only.
- Two confirm/override flags still open for Karthik:
  - `prev()` restarts current song if >3s played (standard convention, not
    in original PRD spec) — confirm keep or remove.
  - Phone song-card stacking layout — implemented per literal PRD wording,
    not yet visually confirmed on a device.
- Drag-preview shows only the thumbnail, not the full row (cosmetic,
  deferred to Sprint 7 per existing decision).
- New backlog item from this session: concurrency test for the playlist
  reorder row-lock — needs a commit-visible test fixture (e.g. adapt the
  `_truncate_all()` pattern) since the current savepoint-rollback fixture
  can't observe cross-connection locking.

## Suggested skills for next session

- `/clean-code`, `/tdd` (as already active) if picking up the concurrency
  test backlog item — will need a new fixture, not just a new test.
- `handoff` again at the end of whatever's next.

No other open threads — Sprint 6 itself is done (`ROADMAP.md`), this was
cleanup on top of it.
