# Handoff — yt-dlp 403 / test-env / MinIO hotfix session

## Context

Repo: `KarthikUdyawar/melo`. Branch: `hotfix/yt-dlp-403-js-runtime`. Solo project. Sprint 6 (Frontend Polish) is done and closed out (see `ROADMAP.md`/`DECISIONS.md`); this was an unsprinted hotfix session triggered by a live production failure.

Conventions in effect: **caveman ultra**, **clean-code**, **tdd**, **ponytail**. Terse responses, minimal diffs, git-diff format on request. Full decision log for this session already lives in `docs/DECISIONS.md`'s "Hotfix — yt-dlp 403 / Test Env" section — not duplicated here, only referenced.

## What happened, in order

1. **Original symptom**: worker log showed `[youtube] No supported JavaScript runtime could be found...` followed by `HTTP Error 403: Forbidden` on download. YouTube now routes more clients through JS-signature solving (confirmed via search — yt-dlp changelog, Feb 2026). Melo's pinned-format-no-JS-runtime workaround (Sprint 1/3) is fragile against this.
2. **yt-dlp bumped** `>=2026.03.17` → `==2026.8.19` in `pyproject.toml`; `uv lock` re-resolved the whole dependency graph (not just yt-dlp), rewriting every pin to exact (`==`). Karthik chose to **keep** the exact pins rather than revert.
3. **Test suite broke as a side effect of timing, not the bump**: `make test` → 49 failed, 120 errors, all SQLite-vs-Postgres confusion (`no such table`, `detached connection fairy`). Root-caused to `.env.test` being **missing from the repo entirely** — `dotenv_values()` silently returns `{}` on a missing file, so `app/core/config.py`'s `force_env_file_priority` validator did nothing, and `tests/unit/conftest.py`'s SQLite env leaked into integration tests run in the same `pytest` process.
4. **`.env.test` recreated** matching `tests/docker-compose.test.yml`'s fixed ports (Postgres 15432, Redis 16379, MinIO 19000/19001). `make test` → **434 passed**, confirmed.
5. **New failure surfaced in GitHub Actions CI**: `pull access denied for minio/minio, repository does not exist`. Root-caused via web search: MinIO pulled all images from Docker Hub/Quay in Oct 2025 (security-CVE dispute) and fully archived the community repo as unmaintained in Feb 2026 — even previously-working pinned tags now 404 on fresh pulls.
6. **Migrated both compose files** (`docker-compose.yml` + `tests/docker-compose.test.yml`) from `minio/minio:RELEASE.2024-05-01T01-11-10Z` to `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z.hotfix.7aa24e772` (Karthik found/confirmed this exact tag pulls; the 2024 tag isn't mirrored on quay). Verified via `make test-integration` — **193/193 passed**.
7. **`docs/TODO.md` and `docs/DECISIONS.md` updated** with all of the above (already applied by Karthik — confirmed matching in this session, no further diff needed).

## Still open — next session should start here

- **The original yt-dlp 403 fix is still unconfirmed.** Everything since step 2 was fixing things the bump *exposed or was blocked by* (test env, MinIO registry) — nobody has yet rebuilt the containers and resubmitted a real failing YouTube URL to see if `yt-dlp==2026.8.19` alone resolves the 403.
  - Next step: `make rebuild` → `make up` → resubmit a real URL → `docker compose logs -f worker`, watch for the "No supported JavaScript runtime" warning and whether 403 still fires.
  - Per the original diagnosis, the JS-runtime warning is a YouTube-side requirement, not a stale-version bug — **expect the bump alone to not be sufficient**. If so, next step is adding a `deno` runtime to the worker Dockerfile, which reverses Sprint 3's "Node.js removed from Dockerfile" decision (needs its own `DECISIONS.md` entry once confirmed working).
- **GitHub Actions CI not yet re-run** against the quay.io MinIO fix — local `make test-integration` passed, but the actual CI runner (the one that produced the original `pull access denied` error) hasn't been confirmed green yet. Push the branch and check the Action.

## Files touched this session

- `pyproject.toml` — yt-dlp bump + full exact-pin rewrite
- `uv.lock` — regenerated (~1800 line diff)
- `.env.test` — created (was missing)
- `docker-compose.yml` — MinIO image → quay.io mirror
- `tests/docker-compose.test.yml` — MinIO image → quay.io mirror
- `docs/TODO.md` — hotfix section added, already applied
- `docs/DECISIONS.md` — new "Hotfix — yt-dlp 403 / Test Env" section added, already applied

## For the next session

- First priority: real-URL retest against rebuilt containers (see "Still open" above) — this determines whether the deno Dockerfile change is needed.
- Second priority: confirm GitHub Actions CI is green on this branch.
- If deno work is needed, read `/mnt/skills/user/ponytail/SKILL.md` first — keep the Dockerfile change minimal (single static binary, no full Node reinstatement).
- Recommended skills for continuation: `caveman` (ultra), `clean-code`, `tdd`, `ponytail` — all standing preferences already in memory.
- Cosmetic, not urgent: local `make test` still spams harmless `Failed to export traces to tempo:4317` DNS-refused noise after test teardown (OTLP exporter threads still trying to flush as pytest exits). Tests pass regardless; add `OTLP_ENDPOINT=` blank to `.env.test` if it bothers Karthik.
