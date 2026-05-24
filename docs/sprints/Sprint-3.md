# Melo — Sprint 3: Speed Processing, Library Features & Metadata UX

**Duration:** Week 3 (Days 15–21)
**Goal:** Enable speed-controlled playback, introduce favorites & playlists, and add a metadata-first UX via preview endpoint.
**Branch strategy:** `develop` base → feature branches → PR → CodeRabbit review → merge

---

## Sprint Goal

> *A user can preview YouTube metadata before ingest, stream audio with trim + speed applied on-the-fly, and organize their library using favorites and playlists.*

---

## Backlog

---

### ✅ FFMPEG-2 — Speed Processing (`atempo`)

**Branch:** `feature/ffmpeg-speed`

* [x] `app/services/processor.py` — `apply_speed(input_path, output_path, speed) -> Path`

  * Use FFmpeg `atempo` filter
  * Constraint: `0.5 ≤ atempo ≤ 2.0` → chain filters when outside range:

    * `speed=4.0` → `atempo=2.0,atempo=2.0`
    * `speed=0.25` → `atempo=0.5,atempo=0.5`
  * Command:

    ```bash
    ffmpeg -i input.mp3 -filter:a "atempo=..." -vn output.mp3
    ```
  * Raise `ProcessingError` on failure
  * Cleanup output on error

* [x] Update `GET /songs/{id}/stream`:

  * Cases:

    1. **No trim, speed=1.0** → direct MinIO stream
    2. **Trim only** → existing flow
    3. **Speed only** → apply `atempo`
    4. **Trim + speed** → trim → then speed
  * Temp pipeline:

    ```text
    original → trimmed → speed-adjusted → stream
    ```

* [x] Ensure:

  * No processing when `speed=1.0`
  * Cleanup in `finally`
  * Generator-based streaming

* [x] Verify:

  * Speed changes perceptibly
  * Combined trim + speed works correctly

---

### ✅ DX-1 — Developer Experience

**Branch:** `feature/dx`

* [x] `CONTRIBUTING.md` — dev setup, branch naming, commit convention, PR checklist, code style, out-of-scope
* [x] `LICENSE` — MIT
* [x] `SECURITY.md` — vuln reporting via GitHub Security Advisories, scope table, security design notes
* [x] `CHANGELOG.md` — full 3-sprint history, Keep a Changelog format
* [x] `.github/ISSUE_TEMPLATE/bug_report.yml` — structured bug report form
* [x] `.github/ISSUE_TEMPLATE/feature_request.yml` — structured feature request form
* [x] `.github/ISSUE_TEMPLATE/config.yml` — disables blank issues, links to docs
* [x] `.github/PULL_REQUEST_TEMPLATE.md` — type, changes, testing, checklist, curl output section
* [x] `.github/workflows/ci.yml` — lint job + unit job + integration job (GitHub-native Postgres service); Codecov upload
* [x] `Makefile` — added `lint`, `fmt`, `reset-db`, `seed`, `clean-tmp`, `backup`, `backup-db`, `backup-minio`, `restore-db`, `restore-minio`, `make help` (default target, `##` annotations on all targets)
* [x] `pyproject.toml` — added `readme`, `license`, `authors`, `keywords`, `classifiers`, `[project.urls]`
* [x] `README.md` — CI/coverage/python/license/pre-commit/ruff badges; `_song_utils.py` in folder structure; backup targets in make table; contributing section; Node.js + dockerignore + `make help` decision log entries
* [x] `docs/ARCHITECTURE.md` — `deleted_at` on all 3 ER models; `DELETE /songs/{id}` in API graph; `_song_utils.py` in folder structure; fixed ` ```test` typo; Sprint 3 decision rows
* [x] `Dockerfile` — removed Node.js (~180MB, unused); `uv sync --frozen --no-install-project` (reproducible from lockfile); pinned uv version (`0.5.21`); `UV_COMPILE_BYTECODE` + `UV_LINK_MODE=copy`
* [x] `.dockerignore` — was empty; now excludes `.git`, `tests/`, `htmlcov/`, `.env*`, `backups/`, dev tooling
* [x] `make seed` — submits 2 sample YouTube songs via API
* [x] `make clean-tmp` — fixed: exec inside worker container (`/tmp/melo` is named volume, not on host)

---

### ✅ DX-2 — Pre-commit, Linting & Type Safety

**Branch:** `feature/dx-precommit`

> Sprint addition — not originally planned but completed this week.

* [x] `.pre-commit-config.yaml` — full hook suite:
  * `pre-commit-hooks` v6.0.0 (trailing whitespace, EOF, YAML/JSON/TOML/AST checks, no-commit-to-branch)
  * `ruff` v0.15.4 with `--fix`
  * `bandit` v1.9.4 — security scan (`# nosec B108 B603 B607` where justified)
  * `gitleaks` v8.30.0 — secret detection
  * `mypy` v1.19.1 with `--strict` + pydantic + sqlalchemy plugins
  * `pytest` on pre-push
* [x] `pyproject.toml` — `[tool.mypy]` config with overrides for `celery`, `minio`, `yt_dlp`, `structlog`, `pydantic_settings`
* [x] All 48 mypy errors resolved across 14 files
* [x] Makefile targets: `pre-commit-install`, `pre-commit`, `pre-commit-all`

---

### ✅ DX-3 — Testing (pytest + coverage)

**Branch:** `feature/dx-tests`

> Sprint addition — not originally planned but completed this week.

* [x] `tests/conftest.py` — root `pytest_configure` hook (env vars before collection), pytest-docker Postgres, rolled-back `db_session` savepoint fixture, `TestClient` with `get_db` override
* [x] `tests/docker-compose.test.yml` — ephemeral Postgres 16 on port 15432 with tmpfs
* [x] `tests/unit/test_schemas.py` — 20 tests
* [x] `tests/unit/test_processor.py` — 18 tests
* [x] `tests/unit/test_storage.py` — 10 tests
* [x] `tests/unit/test_downloader.py` — 11 tests
* [x] `tests/unit/test_preview.py` — 17 tests
* [x] `tests/unit/test_favorites.py` — 18 tests
* [x] `tests/unit/test_playlist_schemas.py` — unit tests
* [x] `tests/integration/test_db.py` — 14 tests
* [x] `tests/integration/test_songs_api.py` — 31 tests
* [x] `tests/integration/test_preview_api.py` — 25 tests
* [x] `tests/integration/test_favorites_api.py` — 17 tests
* [x] `tests/integration/test_playlists_api.py` — integration tests
* [x] Coverage: **94.77%** (threshold: 80%) — `tasks.py` and `celery_app.py` excluded
* [x] Makefile targets: `test`, `test-unit`, `test-integration`, `test-cov`
* [x] Unit test isolation: `_truncate_all()` (savepoint unreliable when endpoints call `db.commit()`)

---

### ✅ DX-4 — Smoke Test

**Branch:** `feature/dx-tests`

> Sprint addition — not originally planned but completed this week.

* [x] `smoke_test.sh` — 24-section end-to-end bash script (requires `curl` + `jq`):
  1. `GET /health`
  2. `POST /songs/preview` → happy path
  3. Preview stateless (song count unchanged)
  4. Preview URL format variants (shorts, youtu.be)
  5. Preview validation errors
  6. `POST /songs` → 202 + song ID
  7. Poll until `status=done` (120s timeout)
  8. `GET /songs/{id}/stream` → 200 + file size check
  9. Favorites lifecycle
  10. Favorites error paths
  11. Songs validation errors
  12. `GET /songs` → count increased
  13. `POST /playlists` → 201
  14. `GET /playlists` → list
  15. `POST /playlists/{id}/songs/{song_id}` → ordering
  16. `GET /playlists/{id}` → ordered songs
  17. `DELETE /playlists/{id}/songs/{song_id}`
  18. Playlist error paths + duplicate idempotency
  19. Same song in multiple playlists
  20–24. Filtering, sorting, cursor pagination
* [x] `make smoke` / `make smoke URL="..."` Makefile target

---

### ✅ DX-5 — CodeRabbit Config

**Branch:** `feature/dx`

* [x] `.coderabbit.yaml` — 11 area labels, 7 label sets, path instructions for all key files, auto-review on `develop`/`master`/`release/*`

---

### ✅ META-2 — Metadata Preview (Pre-Ingest UX)

**Branch:** `feature/metadata-preview`

#### Endpoint

```text
POST /songs/preview
```

#### Request

```json
{ "url": "https://www.youtube.com/watch?v=..." }
```

#### Response (Envelope)

```json
{
  "status_code": 200,
  "message": "Metadata fetched successfully",
  "body": {
    "youtube_id": "abc123",
    "title": "Song title",
    "duration": 213.4,
    "thumbnail_url": "...",
    "channel": "Channel name",
    "upload_date": "2023-10-01"
  }
}
```

#### Implementation

* [x] `probe_metadata(url)` reused in `downloader.py`
* [x] `SongPreviewResponse`, `PreviewRequest` in `schemas/song.py`
* [x] `/songs/preview` declared before `/{song_id}` (route ordering fix)

#### Behavior

* No DB writes, no Celery tasks, pure metadata fetch
* Response time target: <2s

#### Validation

* [x] Invalid URL → 422
* [x] Playlist URL resolves to single video (`noplaylist=True`)
* [x] `duration > 0` verified in smoke test

#### Optional (deferred)

* [ ] Redis cache (TTL 5–10 min): `key: preview:{youtube_id}`

---

### ✅ LIB-1 — Favorites

**Branch:** `feature/favorites`

* [x] `favorites(id, song_id, created_at, deleted_at)` — `unique=True` on `song_id`
* [x] `POST /favorites/{song_id}` — 201 / 200 idempotent / 404
* [x] `DELETE /favorites/{song_id}` — soft delete, 204 / 404
* [x] `GET /favorites` — join Favorite → Song, `created_at DESC`, `is_favorite=True`
* [x] `SongResponse.is_favorite: bool = False` — populated via `_is_favorited()`
* [x] `app/api/favorites.py` registered in `main.py`

---

### ✅ LIB-2 — Playlists

**Branch:** `feature/playlists`

* [x] `playlists(id, name, created_at, deleted_at)` + `playlist_songs(playlist_id, song_id, position)`
* [x] `POST /playlists` — 201
* [x] `GET /playlists` — `paginated_response`, `created_at DESC`
* [x] `GET /playlists/{id}` — songs ordered by `position ASC`, 404
* [x] `POST /playlists/{id}/songs/{song_id}` — append at `max(position)+1`, 201 / 404
* [x] `DELETE /playlists/{id}/songs/{song_id}` — hard delete from join table, 204 / 404
* [x] `app/api/playlists.py` registered in `main.py`
* [x] Bugs fixed: `Mapped[list]` type param, ordering nondeterminism, stale relationship after DELETE

---

### ✅ API-2 — Filtering, Sorting & Search

**Branch:** `feature/api-query`

* [x] `GET /songs` query params: `status`, `favorite`, `search`, `sort_by`, `order`, `limit`, `after`
* [x] DB-level filtering — `SortBy`/`SortOrder` StrEnums
* [x] Indexes: `youtube_id`, `created_at`, `status`, `title` (btree)
* [x] Cursor pagination via `?after=<uuid>` + `bookmark` in response
* [x] `paginated_response` gains `bookmark` kwarg
* [x] All PKs migrated to UUID v7 (`uuid6` package)
* [x] 23 integration tests in `test_songs_api_filtering.py`
* [x] S20–S24 added to smoke test

---

### ✅ API-3 — Computed Fields, UX Polish & Swagger

**Branch:** `feature/api-polish`

#### Slice 1 — `schemas/song.py`
* [x] `_normalize_upload_date` — `"20091025"` → `"2009-10-25"`
* [x] `effective_duration` computed field — `end - start` when both set, else `duration`
* [x] `stream_url: str` — status-driven
* [x] `status: Literal[...]` — replace bare `str`

#### Slice 2 — `api/songs.py`
* [x] `stream_url`: `done → /songs/{id}/stream`, else → `/songs/{id}`

#### Slice 3 — deduplicate `_serialize_song`
* [x] `app/api/_song_utils.py` — `_is_favorited` + `serialize_song`
* [x] `songs.py`, `favorites.py`, `playlists.py` import from `_song_utils`

#### Slice 4 — envelope audit
* [x] `list_favorites` → `envelope_response`
* [x] `list_playlists` → `envelope_response`

#### Slice 5 — soft delete
* [x] `deleted_at: Mapped[datetime | None]` on `Song`, `Favorite`, `Playlist`
* [x] `DELETE /songs/{id}` — soft delete + MinIO `remove_object`
* [x] `DELETE /favorites/{song_id}` — soft delete
* [x] `DELETE /playlists/{id}` — soft delete
* [x] All `GET` queries filter `deleted_at.is_(None)`

#### Slice 6 — quick wins
* [x] `docs_url=None` / `redoc_url=None` in production
* [x] Version from `importlib.metadata`
* [x] `openapi_tags` in `main.py`
* [x] `unhandled_exception_handler` logs via structlog
* [x] Health probes Redis + MinIO + DB
* [x] `schemas/playlist.py`: removed dead `PlaylistSongAdd.position`

#### Slice 7 — Swagger / OpenAPI
* [x] `summary=` on every route
* [x] `responses={404/409/422/502}` on routes that raise them
* [x] Stream endpoint: `openapi_extra` for `audio/mpeg`
* [x] `Field(description=...)` on all `SongResponse` fields
* [x] `Query(description=...)` on all `list_songs` params

---

## Definition of Done

* [x] `/songs/preview` works reliably (<2s)
* [x] Speed processing works (0.5–4.0×)
* [x] Trim + speed combination streams correctly
* [x] Favorites endpoints idempotent and correct
* [x] Playlists support ordering + CRUD
* [x] `/songs` supports filtering, sorting, cursor pagination
* [x] All responses follow envelope format
* [x] No temp file leaks in `/tmp/melo`
* [x] API-3 slices 1–7 complete
* [x] DX-1 complete: CONTRIBUTING, LICENSE, SECURITY, CHANGELOG, GitHub templates, CI workflow, Makefile targets, Dockerfile fixed, .dockerignore populated
* [x] Test suite green — 94.77% coverage
* [x] All branches merged into `develop`
* [x] File moved to `docs/sprints/Sprint-3.md`

---

### Test Fix Notes (post API-3)

9 tests failed after API-3 landed:

| Test                                                     | Root cause                                    | Fix                                            |
| -------------------------------------------------------- | --------------------------------------------- | ---------------------------------------------- |
| `test_delete_removes_row` (unit)                         | Hard-delete assertion; soft delete leaves row | Assert `deleted_at is not None`                |
| `test_song_detail_is_favorite_toggles` (integration)     | `_is_favorited` queried soft-deleted rows     | Added `.filter(Favorite.deleted_at.is_(None))` |
| `test_response_fields` (unit preview)                    | Expected raw `"20091025"`                     | Expect `"2009-10-25"`                          |
| `test_all_metadata_fields_present` (integration preview) | Expected raw `"20091025"`                     | Expect `"2009-10-25"`                          |
| `test_health_contains_db_field` (integration songs)      | Health now enveloped                          | `"db" in body["body"]`                         |
| 4× `TestPlaylistSongAdd` (unit schemas)                  | `position` removed from `PlaylistSongAdd`     | Deleted 4 tests                                |

---

## Out of Scope (→ Sprint 4)

* Frontend UI (Streamlit / React)
* Waveform visualization
* Range streaming (HTTP 206)
* AI recommendations
* Multi-user authentication
* Caching processed variants
* `GET /favorites` cursor pagination

---

## Decision Log

| Decision                                                  | Reason                                                                |
| --------------------------------------------------------- | --------------------------------------------------------------------- |
| UUID v7 for all PKs                                       | String-sortable = chronological = natural cursor key; `uuid6` package |
| Cursor pagination (`after=<uuid>`) on `GET /songs`        | Stable under concurrent inserts; no offset drift                      |
| `bookmark` = last record's `id` or `null`                 | Clients use as next `after`; `null` = end of results                  |
| `count` = total matching before pagination                | Show "42 results" without extra count query                           |
| Preview is stateless                                      | No DB writes, simpler system                                          |
| Still probe in worker                                     | Preview not source of truth                                           |
| Speed applied at stream time                              | Avoid storing variants                                                |
| Chain `atempo` filters                                    | FFmpeg cap: 0.5–2.0 per stage                                         |
| Trim before speed                                         | Correct processing order                                              |
| Favorites idempotent (check-then-insert + IntegrityError) | Clean UX + DB-backed dedup                                            |
| `unique=True` on `favorites.song_id`                      | DB-level dedup regardless of app logic                                |
| `is_favorite` populated per song                          | N+1 acceptable at MVP scale                                           |
| Playlist ordering via `position`                          | Predictable playback; auto-increments                                 |
| Same song reusable across playlists                       | `playlist_songs` scoped per playlist                                  |
| `db.expire_all()` after playlist mutations                | Clears stale SQLAlchemy identity map                                  |
| Ordering test uses explicit `datetime` values             | `server_default=func.now()` resolves identically in transaction       |
| Soft delete on Song, Favorite, Playlist                   | Audit trail; `deleted_at` column; no Alembic migration                |
| `PlaylistSong` hard delete                                | Join table; no audit need                                             |
| `_song_utils.py` shared serializer                        | Eliminates 3 copies; avoids circular import                           |
| `docs_url=None` in production                             | Reduces attack surface                                                |
| Health check add Redis + MinIO                            | Silent infra failure undetectable before                              |
| `DELETE /songs/{id}` + MinIO delete                       | Was in PRD but never implemented                                      |
| Node.js removed from Dockerfile                           | Format selector is plain HTTPS; saved ~180MB + ~40s build             |
| `uv sync --frozen --no-install-project`                   | Reproducible from lockfile; melo is not an installed package          |
| `.dockerignore` populated                                 | Empty file leaked secrets/tests into image context                    |
| `make help` as default target                             | Discoverability for 20+ targets                                       |
| Root `conftest.py` for env setup                          | `pytest_configure` runs before collection                             |
| Unit test isolation via `_truncate_all()`                 | Savepoint unreliable when endpoints call `db.commit()`                |
