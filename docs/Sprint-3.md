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

### ⚡ FFMPEG-2 — Speed Processing (`atempo`)

**Branch:** `feature/ffmpeg-speed`

* [ ] `app/services/processor.py` — `apply_speed(input_path, output_path, speed) -> Path`

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

* [ ] Update `GET /songs/{id}/stream`:

  * Cases:

    1. **No trim, speed=1.0** → direct MinIO stream
    2. **Trim only** → existing flow
    3. **Speed only** → apply `atempo`
    4. **Trim + speed** → trim → then speed
  * Temp pipeline:

    ```
    original → trimmed → speed-adjusted → stream
    ```

* [ ] Ensure:

  * No processing when `speed=1.0`
  * Cleanup in `finally`
  * Generator-based streaming

* [ ] Verify:

  * Speed changes perceptibly
  * Combined trim + speed works correctly

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
* [ ] Speed processing works (0.5–4.0)
* [ ] Trim + speed combination streams correctly
* [ ] Favorites endpoints idempotent and correct
* [ ] Playlists support ordering + CRUD
* [ ] `/songs` supports filtering, sorting, pagination
* [ ] All responses follow envelope format
* [ ] No temp file leaks in `/tmp/melo`
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

| Decision                         | Reason                             |
| -------------------------------- | ---------------------------------- |
| Metadata preview endpoint        | Enables better UX before async job |
| Preview is stateless             | No DB writes, simpler system       |
| Still probe in worker            | Preview not source of truth        |
| Speed applied at stream time     | Avoid storing variants             |
| Chain `atempo` filters           | FFmpeg limitation                  |
| Trim before speed                | Correct processing order           |
| Favorites idempotent             | Clean UX                           |
| Playlist ordering via `position` | Predictable playback               |
| Filtering at DB level            | Scalability                        |
| Computed `effective_duration`    | Reflects real playback             |
| No caching of processed streams  | Keep system simple                 |
| Optional Redis preview cache     | Reduce yt-dlp overhead             |

