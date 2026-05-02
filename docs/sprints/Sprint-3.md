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

    ```
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
* [x] `tests/integration/test_db.py` — 14 tests: Song CRUD, status transitions, dedup query, multi-record scenarios
* [x] `tests/integration/test_songs_api.py` — 31 tests: all `/songs` endpoints, stream cases, validation, 404/409/500/502 error paths
* [x] Coverage: **85.74%** (threshold: 80%) — `tasks.py` and `celery_app.py` excluded (Celery internals)
* [x] Makefile targets: `test`, `test-unit`, `test-integration`, `test-cov`

---

### ✅ DX-4 — Smoke Test

**Branch:** `feature/dx-tests`

> Sprint addition — not originally planned but completed this week.

* [x] `smoke_test.sh` — 10-step end-to-end bash script (requires `curl` + `jq`):
  1. `GET /health`
  2. `GET /songs` baseline count
  3. `POST /songs` → 202 + song ID
  4. `GET /songs/{id}` → detail
  5. Poll until `status=done` (120s timeout)
  6. `GET /songs/{id}/stream` → 200 + file size check
  7. Bad URL → 422
  8. Bad speed → 422
  9. Unknown ID → 404
  10. `GET /songs` → count increased
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

### 🧠 META-2 — Metadata Preview (Pre-Ingest UX)

**Branch:** `feature/metadata-preview`

---

#### 📡 Endpoint

```
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
    "upload_date": "2023-10-01"
  }
}
```

---

#### Implementation

* [ ] `app/services/downloader.py`

  * Reuse `probe_metadata(url)`
  * Ensure:

    * `download=False`
    * `noplaylist=True`
    * pinned format selector
    * raises `DownloadError`

* [ ] Add helper:

  ```python
  def extract_youtube_id(url: str) -> str:
      ...
  ```

* [ ] `app/schemas/song.py`

  ```python
  class SongPreviewResponse(BaseModel):
      youtube_id: str
      title: str | None = None
      duration: float | None = None
      thumbnail_url: str | None = None
      channel: str | None = None
      upload_date: str | None = None
  ```

* [ ] `app/api/songs.py`

  * Add `/songs/preview` endpoint using `envelope_response`

---

#### Behavior

* No DB writes
* No Celery tasks
* Pure metadata fetch
* Response time target: <2s

---

#### Validation

* [ ] Invalid URL → 422
* [ ] Playlist URL resolves to single video
* [ ] `duration > 0`

---

#### Optional (Nice-to-have)

* [ ] Redis cache (TTL 5–10 min):

  ```
  key: preview:{youtube_id}
  ```

---

#### Updated Flow

```
POST /songs/preview → get metadata
        ↓
User decides trim/speed
        ↓
POST /songs → async processing
```

---

### ❤️ LIB-1 — Favorites

**Branch:** `feature/favorites`

* [ ] `favorites(id, song_id, created_at)`

* [ ] `POST /favorites/{song_id}`

  * Idempotent

* [ ] `DELETE /favorites/{song_id}`

* [ ] `GET /favorites`

  * Join with songs

* [ ] Update `SongResponse`:

  ```python
  is_favorite: bool = False
  ```

* [ ] Verify:

  * No duplicate rows
  * Reflects in `/songs`

---

### 📂 LIB-2 — Playlists

**Branch:** `feature/playlists`

* [ ] Models:

  ```
  playlists(id, name, created_at)
  playlist_songs(playlist_id, song_id, position)
  ```

* [ ] `POST /playlists`

* [ ] `GET /playlists`

* [ ] `GET /playlists/{id}`

* [ ] `POST /playlists/{id}/songs/{song_id}`

  * Maintain order via `position`

* [ ] `DELETE /playlists/{id}/songs/{song_id}`

* [ ] Verify:

  * Ordering preserved
  * Same song reusable across playlists

---

### 🔍 API-2 — Filtering, Sorting & Search

**Branch:** `feature/api-query`

* [ ] Enhance `GET /songs`:

Query params:

```
status
favorite=true/false
search
sort_by
order
limit
offset
```

* [ ] DB-level filtering (SQLAlchemy)

* [ ] Add indexes:

  * `youtube_id`
  * `created_at`
  * `status`

* [ ] Response:

```json
{
  "records": [...],
  "count": 42
}
```

* [ ] Verify:

  * Fast queries at scale
  * Case-insensitive search

---

### 🧠 API-3 — Computed Fields & UX Polish

**Branch:** `feature/api-polish`

* [ ] Add computed:

  ```python
  effective_duration = (end - start) if start and end else duration
  ```

* [ ] Normalize:

  * `upload_date: YYYYMMDD → YYYY-MM-DD`

* [ ] Add:

  ```python
  stream_url: str
  ```

* [ ] Ensure envelope compliance everywhere

---

### 🧪 DX-1 — Developer Experience

**Branch:** `feature/dx`

* [ ] `make seed` → sample data

* [ ] `make clean-tmp` → clear `/tmp/melo`

* [ ] Update README:

  * preview endpoint
  * favorites
  * playlists
  * speed streaming

* [ ] Optional:

  * Basic integration test:

    ```
    preview → create → process → stream
    ```

---

## Definition of Done

* [ ] `/songs/preview` works reliably (<2s)
* [x] Speed processing works (0.5–4.0)
* [x] Trim + speed combination streams correctly
* [ ] Favorites endpoints idempotent and correct
* [ ] Playlists support ordering + CRUD
* [ ] `/songs` supports filtering, sorting, pagination
* [x] All responses follow envelope format
* [x] No temp file leaks in `/tmp/melo`
* [ ] All branches merged into `develop`
* [ ] File moved to `melo/docs/sprints/`

---

## Out of Scope (→ Sprint 4)

* Frontend UI (Streamlit / React)
* Waveform visualization
* Range streaming (HTTP 206)
* AI recommendations
* Multi-user authentication
* Caching processed variants

---

## Decision Log

| Decision                                 | Reason                                                                  |
| ---------------------------------------- | ----------------------------------------------------------------------- |
| Metadata preview endpoint                | Enables better UX before async job                                      |
| Preview is stateless                     | No DB writes, simpler system                                            |
| Still probe in worker                    | Preview not source of truth                                             |
| Speed applied at stream time             | Avoid storing variants                                                  |
| Chain `atempo` filters                   | FFmpeg limitation: single stage capped at 0.5–2.0                       |
| Trim before speed                        | Correct processing order                                                |
| Favorites idempotent                     | Clean UX                                                                |
| Playlist ordering via `position`         | Predictable playback                                                    |
| Filtering at DB level                    | Scalability                                                             |
| Computed `effective_duration`            | Reflects real playback                                                  |
| No caching of processed streams          | Keep system simple                                                      |
| Optional Redis preview cache             | Reduce yt-dlp overhead                                                  |
| `class Envelope[T]` requires Python 3.12 | PEP 695 syntax — confirmed `requires-python = ">=3.12"` in pyproject    |
| `# nosec B108/B603/B607` in processor    | `/tmp/melo` is intentional; subprocess args are internal constants only |
| `tasks.py` excluded from coverage        | Celery task internals require running worker — covered by smoke test    |
| Savepoint pattern in test `db_session`   | Rolls back per-test without truncation; works with SQLAlchemy nested tx |
| Root `conftest.py` for env setup         | `pytest_configure` at root runs before collection — only reliable hook  |
