# Handoff — yt-dlp 403 hotfix + test env fix

## Context

Repo: `KarthikUdyawar/melo`. Branch: `hotfix/yt-dlp-403-js-runtime`. Solo project. Sprint 6 not yet scoped (see `ROADMAP.md`/`TODO.md`). This session was an unsprinted hotfix, triggered by a YouTube download failure reported live in production logs.

Conventions in effect: **caveman ultra**, **clean-code**, **tdd**, **ponytail**. Terse responses, minimal diffs, git-diff format on request.

## What happened, in order

1. **Symptom**: worker log showed `[youtube] No supported JavaScript runtime could be found...` warning, immediately followed by `ERROR: unable to download video data: HTTP Error 403: Forbidden` on `process_song_task`. UI showed songs stuck in `failed`.
2. **Diagnosis**: not a stale-version bug — YouTube now routes more clients through JS-signature solving (confirmed via yt-dlp changelog search, Feb 2026 entry: "youtube: Default to tvplayer JS variant"). Melo's Sprint 1/3 workaround (pinned format IDs, no JS runtime, Node.js removed for image-size savings) is now fragile against this YouTube-side change.
3. **Attempted fix**: bumped `yt-dlp` pin `>=2026.03.17` → `>=2026.08.19` (latest stable at the time) in `pyproject.toml`, ran `uv lock`.
4. **Side effect**: `uv lock` re-resolved the *entire* dependency graph, not just yt-dlp — `pyproject.toml` came back with every dependency rewritten to exact pins (`==`), and the lockfile diff was ~1800 lines changed. Karthik decided to **keep the exact pins** rather than revert, since the suite was later confirmed green against them.
5. **Test suite exploded**: `make test` → 49 failed, 120 errors. Tracebacks showed SQLite errors (`no such table: playlists`) inside *Postgres-only* integration tests, plus "detached connection fairy" and "closed database" errors.
6. **Root-caused** (not a regression from the bump — coincidental timing): `.env.test` was **missing from the repo entirely**. `app/core/config.py`'s `force_env_file_priority` validator calls `dotenv_values(_env_file())`, which silently returns `{}` for a missing file — no error, no warning. With nothing to force `.env.test`'s Postgres `DATABASE_URL` back into settings, whatever `tests/unit/conftest.py` had set in `os.environ` (SQLite) leaked through into integration tests, since `make test` runs unit + integration in one `pytest` process.
7. **Fix**: recreated `.env.test` with values matching `tests/docker-compose.test.yml`'s fixed ports (Postgres `15432`, Redis `16379`, MinIO `19000`/`19001`, `songs-test` bucket, blank `PYROSCOPE_SERVER_URL` to suppress noise).
8. **Result**: `make test` → **434 passed**, 0 failed. Confirmed via Karthik pasting the full pytest run.
9. **Decision made**: keep `pyproject.toml`'s exact pins (already locked + green) rather than revert to ranges.

## Open items — **not yet confirmed**

- **The actual yt-dlp fix is unverified.** We bumped the version and fixed an unrelated test-env bug, but never confirmed the original 403 is resolved. Karthik was told to:
  1. `make rebuild` (rebuild worker/api images with the new lockfile)
  2. `make up`
  3. Resubmit a real YouTube URL
  4. Tail `docker compose logs -f worker`, check whether the "No supported JavaScript runtime" warning still fires and whether it still 403s
- **If the bump alone doesn't fix it** (likely, per the diagnosis in step 2 — this is a YouTube-side JS-runtime requirement, not a stale-code bug): next step is adding a `deno` JS runtime to the worker Dockerfile. This **reverses** the Sprint 3 decision "Node.js removed from Dockerfile ... saved ~180MB and ~40s build time" — deno is a single static binary, not Node/npm, so the size hit should be much smaller, but this needs a new `DECISIONS.md` entry once done.
- Optional, not urgent: `.env.test` doesn't set `OTLP_ENDPOINT`, so local `make test` runs spam harmless `Failed to export traces to tempo:4317` DNS-refused noise (tempo isn't part of the test compose file). Cosmetic only — tests still pass. Add `OTLP_ENDPOINT=` blank to `.env.test` if it bothers Karthik.

## Files touched this session

- `pyproject.toml` — yt-dlp bump + full exact-pin rewrite (kept)
- `uv.lock` — regenerated, ~1800 line diff
- `.env.test` — **created** (was missing), 15 lines, matches `tests/docker-compose.test.yml`
- `docs/TODO.md` — hotfix section added
- `docs/DECISIONS.md` — new unsprinted "Hotfix — yt-dlp 403 / Test Env" section added

## For the next session

- First priority: get the worker log from a real retest and confirm/deny whether 403 persists. This determines whether the deno Dockerfile change is needed.
- If deno is needed: will touch `Dockerfile` (root, worker build stage) — read `/mnt/skills/user/ponytail/SKILL.md` first, keep the change minimal (just the runtime binary + any yt-dlp extractor-arg needed, no full Node reinstatement).
- Recommended skills for continuation: `caveman` (ultra), `clean-code`, `tdd`, `ponytail` — all already standing preferences.
- `.env.test` is now a real file in the repo — if Karthik's `.gitignore` excludes `.env.*` patterns, confirm `.env.test` isn't accidentally ignored again (it holds no real secrets, just fixed test-compose ports/creds, so it's fine to commit, but worth a sanity check since it went missing once already).
