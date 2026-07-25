# Handoff — Melo Sprint 6 planning (Frontend Polish)

## Context

Repo: `KarthikUdyawar/melo`. Solo project. Sprint 5 (Observability) done and closed out — see prior handoff/`DECISIONS.md`. This session planned **Sprint 6: Frontend Polish**, scope decided via elicitation (Karthik picked all proposed areas, no fixed timeline).

Conventions in effect: **caveman ultra**, **clean-code**, **TDD**.

## What this session produced

- `docs/PRD.md` (rewritten for Sprint 6) — full spec: problem/goal/scope, FE-0…FE-6 ticket breakdown with deps, decision log. Currently in `/mnt/user-data/outputs/PRD.md`, not yet placed in repo by Karthik.
- `docs/TODO.md` (rewritten) — Sprint 6 checklist mirroring PRD tickets, plus a Sprint 7+ candidates section. Currently in `/mnt/user-data/outputs/TODO.md`, not yet placed in repo.

Read those two files for full ticket detail — not duplicated here.

## Scope decided (don't re-litigate)

- **Reverses Sprint 4's "no mobile" decision.** Responsive layout now in scope: desktop >=1280px (unchanged), tablet 768-1279px, phone <=767px.
- All 6 proposed areas are must-have this sprint, no fixed deadline: responsive layout (FE-0), player features -- volume/shuffle/loop/autoplay (FE-1), drag-reorder playlists (FE-2), waveform display (FE-3), accessibility audit (FE-4), UX bug fixes (FE-5, audit-driven).
- Order: **FE-0 first** (foundation), rest cascade per PRD's dependency table.
- FE-2 reorder API: single-song `PATCH /playlists/{id}/songs/{song_id}` with `{"position": int}` -- Karthik's explicit choice over a bulk ordered-list endpoint, accepts N calls on multi-move.
- FE-5 has no pre-supplied bug list -- audit-as-you-go, log findings into `TODO.md`.
- Waveform: client-side only (Web Audio API, in-memory cache), no backend/storage change -- keeps Sprint 2/3's "no stored variants" philosophy.
- No automated frontend tests introduced -- Sprint 4's "no framework = no component test surface" decision still holds; only FE-2's new backend endpoint gets TDD (unit + integration).

## Two open questions -- need Karthik's answer before starting

1. **Waveform placement** (blocks FE-3): inline in the existing 72px player bar vs. an expandable "now playing" panel. PRD defaults to inline; flagged in both `PRD.md` and `TODO.md` for confirmation.
2. **Nav pattern** (blocks FE-0): bottom tab bar (phone) + icon rail/drawer (tablet) vs. plain hamburger on both tiers. PRD defaults to the former.

## For the next session

- If Karthik confirms/overrides the two open questions above, update `PRD.md`'s Decision Log and `TODO.md`'s "Blocking" section accordingly before any code starts.
- Start with FE-0 (responsive layout) per the dependency order -- everything else builds on it.
- If Karthik shares actual repo files (CSS/`app.js`/`player.js`/`components.js`), verify current markup against `DESIGN.md`/`SERVICES.md` before editing -- standing "verify before writing" principle.
- FE-2 is the only ticket needing backend TDD -- read `/mnt/skills/user/tdd/SKILL.md` first when that ticket starts.
- Recommended skills: `caveman` (ultra), `clean-code`, `tdd` -- Karthik's standing preference.
- Suggested feature branch: `feature/sprint6-frontend-polish` (see chat reply for naming rationale).
