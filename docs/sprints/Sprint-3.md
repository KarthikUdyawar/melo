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
* [x] All 48 mypy errors resolved across 14 files:
  * `Generic[T]` syntax fixed for Python 3.11 compat → `class Envelope[T]` (3.12 only confirmed)
  * `force_env_file_priority` typed as `dict[str, Any]`
  * `_BaseTask(Task[tuple[...], dict[str, object]])` → `# type: ignore[type-arg]`
  * `probe_metadata` return typed as `SongMeta` TypedDict
  * All subprocess calls annotated with `# nosec`
* [x] Makefile targets: `pre-commit-install`, `pre-commit`, `pre-commit-all`

---

### ✅ DX-3 — Testing (pytest + coverage)

**Branch:** `feature/dx-tests`

> Sprint addition — not originally planned but completed this week.

* [x] `tests/conftest.py` — root `pytest_configure` hook (env vars before collection), pytest-docker Postgres, rolled-back `db_session` savepoint fixture, `TestClient` with `get_db` override
* [x] `tests/docker-compose.test.yml` — ephemeral Postgres 16 on port 15432 with tmpfs
* [x] `tests/unit/test_schemas.py` — 20 tests: URL validation (valid/invalid), speed bounds, trim range logic, `SongResponse` construction
* [x] `tests/unit/test_processor.py` — 18 tests: `_build_atempo_filters` chain correctness, `trim_audio` stream-copy/fallback/cleanup, `apply_speed` success/failure/cleanup
* [x] `tests/unit/test_storage.py` — 10 tests: `ensure_bucket_exists`, `upload_file`, `get_presigned_url` (all with mocked Minio)
* [x] `tests/unit/test_downloader.py` — 11 tests: `probe_metadata`, `download_audio` (mocked yt-dlp)
* [x] `tests/unit/test_preview.py` — 17 tests: `extract_youtube_id` URL formats, `/songs/preview` endpoint (success, 502, 422, stateless, sparse metadata)
* [x] `tests/unit/test_favorites.py` — 18 tests: POST/DELETE/GET favorites, idempotency, 404 paths, `is_favorite` in song responses
* [x] `tests/unit/test_playlist_schemas.py` — unit tests: schema validation for playlist create/response, position ordering
* [x] `tests/integration/test_db.py` — 14 tests: Song CRUD, status transitions, dedup query, multi-record scenarios
* [x] `tests/integration/test_songs_api.py` — 31 tests: all `/songs` endpoints, stream cases, validation, 404/409/500/502 error paths
* [x] `tests/integration/test_preview_api.py` — 25 tests: happy path, URL variants, validation, error paths, stateless guarantee
* [x] `tests/integration/test_favorites_api.py` — 17 tests: lifecycle, idempotency, error paths, `is_favorite` reflected in `/songs`
* [x] `tests/integration/test_playlists_api.py` — integration tests: full playlist CRUD, ordering, multi-playlist reuse, edge cases
* [x] Coverage: **94.77%** (threshold: 80%) — `tasks.py` and `celery_app.py` excluded (Celery internals)
* [x] Makefile targets: `test`, `test-unit`, `test-integration`, `test-cov`
* [x] Unit test isolation: switched from savepoint rollback to `_truncate_all()` (PRAGMA FK OFF → delete all tables → FK ON) — savepoint unreliable when endpoints call `db.commit()`

---

### ✅ DX-4 — Smoke Test

**Branch:** `feature/dx-tests`

> Sprint addition — not originally planned but completed this week.

* [x] `smoke_test.sh` — 24-section end-to-end bash script (requires `curl` + `jq`):
  1. `GET /health`
  2. `POST /songs/preview` → happy path (youtube_id, title, duration, envelope shape)
  3. Preview stateless (song count unchanged)
  4. Preview URL format variants (shorts, youtu.be)
  5. Preview validation errors (non-YouTube, missing url, homepage → 422)
  6. `POST /songs` → 202 + song ID
  7. Poll until `status=done` (120s timeout)
  8. `GET /songs/{id}/stream` → 200 + file size check
  9. Favorites lifecycle (POST 201 → POST 200 idempotent → GET list → DELETE 204 → is_favorite toggles)
  10. Favorites error paths (unknown song → 404, not-favorited → 404)
  11. Songs validation (bad URL → 422, bad speed → 422, unknown ID → 404)
  12. `GET /songs` → count increased
  13. `POST /playlists` → 201 + playlist ID
  14. `GET /playlists` → list includes new playlist
  15. `POST /playlists/{id}/songs/{song_id}` → 201, ordering preserved
  16. `GET /playlists/{id}` → songs in correct position order
  17. `DELETE /playlists/{id}/songs/{song_id}` → 204, song removed
  18. Playlist error paths (unknown playlist → 404, unknown song → 404) + duplicate add idempotency (→ 200)
  19. Same song reusable across multiple playlists
  20. S20–S24: filtering, sorting, cursor pagination (`after=`, `status=`, `favorite=`, `search=`, `sort_by=`)
* [x] `make smoke` / `make smoke URL="..."` Makefile target

---

### ✅ DX-5 — CodeRabbit Config

**Branch:** `feature/dx`

> Sprint addition — not originally planned but completed this week.

* [x] `.coderabbit.yaml` — full Melo-specific config:
  * 11 area labels, 7 type/risk/size/status/priority label sets
  * Path instructions for all key files: `tasks.py`, `processor.py`, `downloader.py`, `songs.py`, `storage.py`, `db.py`, `schemas/song.py`, `config.py`, `tests/`, `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `.pre-commit-config.yaml`
  * Auto-review on `develop`, `main`, `release/*`

---

### ✅ META-2 — Metadata Preview (Pre-Ingest UX)

**Branch:** `feature/metadata-preview`

---

#### 📡 Endpoint

```text
POST /songs/preview
```

#### Request

```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
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
    "upload_date": "20231001"
  }
}
```

---

#### Implementation

* [x] `app/services/downloader.py`

  * Reuse `probe_metadata(url)`
  * `download=False`, `noplaylist=True`, pinned format selector, raises `DownloadError`
  * `extract_youtube_id(url: str) -> str` — supports `?v=`, `youtu.be`, `/shorts/`, `/embed/`, `/live/`

* [x] `app/schemas/song.py` — `SongPreviewResponse`, `PreviewRequest`

* [x] `app/api/songs.py` — `/songs/preview` before `/{song_id}` (route ordering)

---

#### Behavior

* No DB writes
* No Celery tasks
* Pure metadata fetch
* Response time target: <2s

---

#### Validation

* [x] Invalid URL → 422
* [x] Playlist URL resolves to single video (`noplaylist=True`)
* [x] `duration > 0` verified in smoke test

---

#### Optional (Nice-to-have)

* [ ] Redis cache (TTL 5–10 min):

  ```text
  key: preview:{youtube_id}
  ```

---

#### Updated Flow

```text
POST /songs/preview → get metadata
        ↓
User decides trim/speed
        ↓
POST /songs → async processing
```

---

### ✅ LIB-1 — Favorites

**Branch:** `feature/favorites`

* [x] `favorites(id, song_id, created_at)` — `unique=True` on `song_id` (one row per song)

* [x] `POST /favorites/{song_id}`

  * 201 on create, 200 if already favorited (idempotent)
  * 404 if song not found

* [x] `DELETE /favorites/{song_id}`

  * 204 on success
  * 404 if song not found or not favorited

* [x] `GET /favorites`

  * Join `Favorite → Song`, ordered by `favorite.created_at DESC`
  * Returns `paginated_response` with `is_favorite=True` on all records

* [x] `SongResponse.is_favorite: bool = False`

  * Populated via `_is_favorited()` query in `_serialize()`
  * Reflected in `GET /songs` and `GET /songs/{id}`

* [x] Verify:

  * [x] No duplicate rows (DB `unique=True` + check-then-insert)
  * [x] `is_favorite` reflects in `/songs` and `/songs/{id}`
  * [x] Toggle: POST → True, DELETE → False

* [x] `app/api/favorites.py` — new router registered in `app/main.py`

---

### ✅ LIB-2 — Playlists

**Branch:** `feature/playlists`

* [x] Models:

  ```text
  playlists(id, name, created_at)
  playlist_songs(playlist_id, song_id, position)
  ```

* [x] `POST /playlists`

  * 201 on create
  * Returns `{id, name, created_at, songs: []}`

* [x] `GET /playlists`

  * Returns `paginated_response` ordered by `created_at DESC`

* [x] `GET /playlists/{id}`

  * Returns playlist detail with songs ordered by `position ASC`
  * 404 if not found

* [x] `POST /playlists/{id}/songs/{song_id}`

  * Appends song at next position (`max(position) + 1`)
  * 201 on success
  * 404 if playlist or song not found

* [x] `DELETE /playlists/{id}/songs/{song_id}`

  * 204 on success
  * 404 if playlist not found or song not in playlist

* [x] `app/api/playlists.py` — new router registered in `app/main.py`

* [x] Bugs fixed during TDD loop:

  * `Mapped[list]` missing type param → `Mapped[list["Song"]]` + `# type: ignore[type-arg]`
  * Unused `type: ignore` removed from `_serialize_playlist_detail`
  * Ordering test nondeterminism → explicit `datetime(...)` values instead of `server_default`
  * Stale relationship after DELETE → `db.expire_all()` after commit in `remove_song_from_playlist`

* [x] Verify:

  * [x] Ordering preserved across add/remove cycles
  * [x] Same song reusable across multiple playlists
  * [x] `position` auto-increments correctly

---

### ✅ API-2 — Filtering, Sorting & Search

**Branch:** `feature/api-query`

* [x] Enhance `GET /songs`:

Query params:

```text
status
favorite=true/false
search
sort_by
order
limit
after        (cursor — UUID v7 of last seen record)
```

* [x] DB-level filtering (SQLAlchemy) — `SortBy` / `SortOrder` StrEnums; `ColumnElement[Any]` return types

* [x] Add indexes:

  * `youtube_id`
  * `created_at`
  * `status`
  * `title` (btree)

* [x] **Cursor-based pagination** via `?after=<uuid>`:

  * Looks up anchor row → `col > anchor_val` (asc) or `col < anchor_val` (desc)
  * Stable under concurrent inserts; no offset drift

* [x] Response:

```json
{
  "records": [...],
  "count": 42,
  "bookmark": "<last-uuid-or-null>"
}
```

* [x] `app/api/responses.py` — `paginated_response` gains `bookmark` kwarg (default `None`)

* [x] `tests/integration/test_songs_api_filtering.py` — **NEW** — 23 tests, 5 TDD slices

* [x] `tests/smoke_test.sh` — S20–S24 added (sections 19 → 24)

* [x] `pyproject.toml` — added `uuid6>=2025.0.1` dependency (`uv add uuid6`)

* [x] All model PKs migrated to **UUID v7** (via `uuid6` package) — string-sortable = chronological = natural cursor key

* [x] Verify:

  * Fast queries at scale
  * Case-insensitive search

---

### ✅ API-3 — Computed Fields, UX Polish & Swagger

**Branch:** `feature/api-polish`

#### Slice 1 — `schemas/song.py`

* [x] `_normalize_upload_date(v)` module-level fn:
  * `None → None`, `"20091025" → "2009-10-25"`, already ISO → passthrough, malformed → passthrough
* [x] `@field_validator("upload_date", mode="before")` on `SongResponse` and `SongPreviewResponse`
* [x] `effective_duration: float | None` — `@model_validator(mode="after")`: `end - start` if both set, else `duration`
* [x] `stream_url: str` — passed at construction, status-driven in `_serialize`
* [x] `status: Literal["pending","processing","done","failed"]` — replace bare `str`

#### Slice 2 — `api/songs.py` `_serialize`

* [x] `stream_url`: `done → /songs/{id}/stream`, else → `/songs/{id}`
* [x] Pass `stream_url` into `SongResponse` constructor

#### Slice 3 — deduplicate `_serialize_song`

* [x] Created `app/api/_song_utils.py` — `_is_favorited` + `serialize_song` centralised here
* [x] `songs.py`, `favorites.py`, `playlists.py` import from `_song_utils`

#### Slice 4 — envelope audit

* [x] `favorites.list_favorites` → `envelope_response`
* [x] `playlists.list_playlists` → `envelope_response`

#### Slice 5 — soft delete

* [x] Added `deleted_at: Mapped[datetime | None]` to `Song`, `Favorite`, `Playlist`
  * `DateTime(timezone=True)`, nullable, default `None`
  * No migration needed — `create_all(checkfirst=True)` on startup handles new column
* [x] `DELETE /songs/{id}` — **new endpoint** (was in PRD, never implemented):
  * Soft delete: `song.deleted_at = datetime.now(UTC)`
  * Also calls MinIO `remove_object(bucket, song.file_url)` if `file_url` set
  * 404 if not found or already deleted
  * 204 on success
* [x] `DELETE /favorites/{song_id}` — changed to soft delete
* [x] `DELETE /playlists/{id}` — changed to soft delete
* [x] `PlaylistSong` — hard delete stays (join table, no audit need)
* [x] All `GET` queries add `.filter(Model.deleted_at.is_(None))` guard

#### Slice 6 — quick wins

* [x] `main.py`: `docs_url=None` / `redoc_url=None` when `is_production`
* [x] `main.py`: version from `importlib.metadata.version("melo")`
* [x] `main.py`: `openapi_tags` list with name + description per router
* [x] `exception_handlers.py`: `logger.exception("unhandled_error", path=...)` in `unhandled_exception_handler`
* [x] `health`: added `ping_redis()` + `ping_minio()` alongside `ping_db()`; wrapped in `envelope_response`
* [x] Makefile: `make clean-tmp` → `rm -rf /tmp/melo`
* [x] `schemas/playlist.py`: removed dead `PlaylistSongAdd.position` field

#### Slice 7 — Swagger / OpenAPI

* [x] `summary=` on every `@router.X` decorator
* [x] `responses={404: ..., 409: ..., 422: ..., 502: ...}` on routes that raise them
* [x] Stream endpoint: `openapi_extra` for `audio/mpeg` response
* [x] `Field(description=...)` on all `SongResponse` fields
* [x] `Query(description=...)` on all `list_songs` filter params

---

### 🧪 DX-1 — Developer Experience

**Branch:** `feature/dx`

* [ ] `make seed` → sample data (→ Sprint 4)

* [ ] `make clean-tmp` → clear `/tmp/melo` (moved into API-3 Slice 6)

* [x] Update README:

  * [x] preview endpoint
  * [x] favorites
  * [x] playlists
  * [x] `DELETE /songs/{id}` in API table
  * [x] `make clean-tmp` in Makefile targets
  * [x] API-3 decision log entries added
  * [x] Out of Scope updated (API-3 complete)

* [ ] Optional:

  * Basic integration test:

    ```text
    preview → create → process → stream
    ```

---

## Definition of Done

* [x] `/songs/preview` works reliably (<2s)
* [x] Speed processing works (0.5–4.0)
* [x] Trim + speed combination streams correctly
* [x] Favorites endpoints idempotent and correct
* [x] Playlists support ordering + CRUD
* [x] `/songs` supports filtering, sorting, cursor pagination
* [x] All responses follow envelope format
* [x] No temp file leaks in `/tmp/melo`
* [x] API-3 slices 1–7 complete
* [x] Test suite green (9 failures fixed — see test fix notes below)
* [ ] All branches merged into `develop`
* [ ] File moved to `melo/docs/sprints/`

### Test fix notes (post API-3)

9 tests failed after API-3 landed because they asserted pre-API-3 behaviour:

| Test                                                     | Root cause                                                | Fix                                                                           |
| -------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `test_delete_removes_row` (unit)                         | Hard-delete assertion; soft delete leaves row             | Assert `deleted_at is not None` instead of `count == 0`                       |
| `test_song_detail_is_favorite_toggles` (integration)     | `_is_favorited` queried all rows incl. soft-deleted       | Added `.filter(Favorite.deleted_at.is_(None))` to `_song_utils._is_favorited` |
| `test_response_fields` (unit preview)                    | Expected raw `"20091025"`                                 | Expect normalized `"2009-10-25"`                                              |
| `test_all_metadata_fields_present` (integration preview) | Expected raw `"20091025"`                                 | Expect normalized `"2009-10-25"`                                              |
| `test_health_contains_db_field` (integration songs)      | `"db" in body` — health now enveloped                     | `"db" in body["body"]`                                                        |
| 4× `TestPlaylistSongAdd` (unit schemas)                  | `position` field removed from `PlaylistSongAdd` (Slice 6) | Deleted the 4 tests                                                           |

---

## Out of Scope (→ Sprint 4)

* Frontend UI (Streamlit / React)
* Waveform visualization
* Range streaming (HTTP 206)
* AI recommendations
* Multi-user authentication
* Caching processed variants
* `GET /favorites` cursor pagination
* `make seed`

---

## Decision Log

| Decision                                                                | Reason                                                                                                                                              |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| UUID v7 for all PKs                                                     | String-sortable = chronological = natural cursor key; `uuid6` package used                                                                          |
| Cursor pagination (`after=<uuid>`) on `GET /songs`                      | Stable under concurrent inserts; no offset drift vs `OFFSET`-based pagination                                                                       |
| `bookmark` = last record's `id` or `null`                               | Clients use it as the next `after` param; `null` signals end of results                                                                             |
| `count` = total matching before pagination                              | Lets clients show "42 results" without a separate count query                                                                                       |
| Cursor tie-breaking on `title`/`duration` deferred                      | Secondary sort on `id` deferred to API-3                                                                                                            |
| Metadata preview endpoint                                               | Enables better UX before async job                                                                                                                  |
| Preview is stateless                                                    | No DB writes, simpler system                                                                                                                        |
| Still probe in worker                                                   | Preview not source of truth                                                                                                                         |
| Speed applied at stream time                                            | Avoid storing variants                                                                                                                              |
| Chain `atempo` filters                                                  | FFmpeg limitation: single stage capped at 0.5–2.0                                                                                                   |
| Trim before speed                                                       | Correct processing order                                                                                                                            |
| Favorites idempotent (check-then-insert + IntegrityError handling)      | Clean UX with DB-backed dedup and safe behavior under concurrent requests                                                                           |
| `unique=True` on `favorites.song_id`                                    | DB-level dedup guarantee regardless of app logic                                                                                                    |
| `is_favorite` populated with prefetched favorites in list serialization | Avoid N+1 in `/songs`; keep single-record paths simple                                                                                              |
| `DELETE /favorites` returns 204                                         | No body on delete; 404 if not favorited for explicit error feedback                                                                                 |
| Playlist ordering via `position`                                        | Predictable playback; auto-increments on add                                                                                                        |
| Same song reusable across playlists                                     | `playlist_songs` scoped per playlist; no uniqueness constraint on `song_id` alone                                                                   |
| `db.expire_all()` after playlist mutations                              | Clears stale relationship state from SQLAlchemy identity map post-commit                                                                            |
| Ordering test uses explicit `datetime` values                           | `server_default=func.now()` resolves identically within a transaction — order nondeterministic without explicit timestamps                          |
| Filtering at DB level                                                   | Scalability                                                                                                                                         |
| Computed `effective_duration`                                           | Reflects real playback length after trim                                                                                                            |
| `stream_url` relative path                                              | No config dependency; works regardless of deployment base URL                                                                                       |
| `stream_url` status-driven not nullable                                 | Always a usable URL — client polls `GET /songs/{id}` until done, then streams                                                                       |
| No `GET /songs/{id}/status` endpoint                                    | `GET /songs/{id}` already returns status; no new endpoint needed                                                                                    |
| Soft delete on Song, Favorite, Playlist                                 | Safer than hard delete; preserves audit trail; `deleted_at` column                                                                                  |
| `PlaylistSong` hard delete stays                                        | Join table; no user-facing audit need; position logic unaffected                                                                                    |
| `_song_utils.py` shared serializer                                      | Eliminates three copies of `_serialize_song`; avoids circular import                                                                                |
| `docs_url=None` in production                                           | Swagger not needed in production; reduces attack surface                                                                                            |
| `unhandled_exception_handler` add logger                                | 500s currently invisible in structured logs                                                                                                         |
| Health check add Redis + MinIO                                          | Silent infrastructure failure undetectable via `/health` today                                                                                      |
| `DELETE /songs/{id}` + MinIO delete                                     | Endpoint was in PRD but never implemented; MinIO object freed alongside soft delete                                                                 |
| No caching of processed streams                                         | Keep system simple                                                                                                                                  |
| Optional Redis preview cache                                            | Reduce yt-dlp overhead on repeated previews                                                                                                         |
| `class Envelope[T]` requires Python 3.12                                | PEP 695 syntax — confirmed `requires-python = ">=3.12"` in pyproject                                                                                |
| `# nosec B108/B603/B607` in processor                                   | `/tmp/melo` is intentional; subprocess args are internal constants only                                                                             |
| `tasks.py` excluded from coverage                                       | Celery task internals require running worker — covered by smoke test                                                                                |
| Unit test isolation via `_truncate_all()`                               | Savepoint rollback unreliable when endpoints call `db.commit()` (releases savepoint); truncate-after-test is simpler and reliable                   |
| Ordering test omitted from unit suite                                   | SQLite `func.now()` resolves once per transaction — timestamps identical, order nondeterministic; ordering verified in integration tests (Postgres) |
| Root `conftest.py` for env setup                                        | `pytest_configure` at root runs before collection — only reliable hook                                                                              |
