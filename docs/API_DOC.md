# Melo — API Reference

> Base URL: `http://localhost:8000`
> All responses use the **envelope format** unless noted.

---

## Envelope Format

Every response (except streams and 204s) wraps its payload:

```json
{
  "status_code": 200,
  "message": "Human-readable message.",
  "body": { ... }
}
```

Paginated list responses put the list inside `body`:

```json
{
  "status_code": 200,
  "message": "...",
  "body": {
    "records": [ ...items ],
    "count": 42,
    "bookmark": "<uuid-or-null>"
  }
}
```

`bookmark` is the `id` of the last record returned. Pass as `?after=<bookmark>` for the next page. `null` = end of results.

---

## Song Object

All song-returning endpoints share this shape:

```json
{
  "id": "019487ab-...",
  "title": "Rick Astley - Never Gonna Give You Up",
  "youtube_id": "dQw4w9WgXcQ",
  "file_url": "songs/019487ab-....mp3",
  "duration": 213.0,
  "start": 10.0,
  "end": 60.0,
  "speed": 1.5,
  "status": "done",
  "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/...",
  "channel": "RickAstleyVEVO",
  "upload_date": "2009-10-25",
  "created_at": "2024-01-15T10:30:00.000000",
  "is_favorite": false,
  "stream_url": "/songs/019487ab-.../stream",
  "effective_duration": 50.0
}
```

| Field                | Type                                              | Notes                                              |
| -------------------- | ------------------------------------------------- | -------------------------------------------------- |
| `id`                 | `string` (UUID v7)                                | Chronologically sortable                           |
| `title`              | `string \| null`                                  | Populated after processing                         |
| `youtube_id`         | `string \| null`                                  | 11-char YouTube ID                                 |
| `file_url`           | `string \| null`                                  | MinIO object path                                  |
| `duration`           | `number \| null`                                  | Full audio length in seconds                       |
| `start`              | `number \| null`                                  | Trim start offset (seconds)                        |
| `end`                | `number \| null`                                  | Trim end offset (seconds)                          |
| `speed`              | `number`                                          | 0.5–4.0, default 1.0                               |
| `status`             | `"pending" \| "processing" \| "done" \| "failed"` |                                                    |
| `thumbnail_url`      | `string \| null`                                  | YouTube thumbnail                                  |
| `channel`            | `string \| null`                                  | YouTube channel name                               |
| `upload_date`        | `string \| null`                                  | ISO 8601 `YYYY-MM-DD`                              |
| `created_at`         | `string`                                          | ISO 8601 timestamp                                 |
| `is_favorite`        | `boolean`                                         |                                                    |
| `stream_url`         | `string`                                          | `/songs/{id}/stream` when done, else `/songs/{id}` |
| `effective_duration` | `number \| null`                                  | `end - start` if both set, else `duration`         |

---

## Songs

### `POST /songs/preview`

Fetch YouTube metadata without persisting anything. Use before submitting to let the user confirm trim/speed params.

**Request body:**
```json
{ "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }
```

**Response `200`:**
```json
{
  "status_code": 200,
  "message": "Metadata fetched successfully.",
  "body": {
    "youtube_id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": 213.0,
    "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "channel": "RickAstleyVEVO",
    "upload_date": "2009-10-25"
  }
}
```

| Status | Meaning             |
| ------ | ------------------- |
| `200`  | Metadata returned   |
| `422`  | Invalid YouTube URL |
| `502`  | yt-dlp fetch failed |

Supported URL formats: `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`, `youtube.com/embed/`, `youtube.com/live/`

---

### `POST /songs`

Submit a YouTube URL for async download and processing. Returns `202` immediately.

**Request body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "start": 10,
  "end": 60,
  "speed": 1.5
}
```

| Field   | Type     | Required | Constraints              |
| ------- | -------- | -------- | ------------------------ |
| `url`   | `string` | ✅        | Valid YouTube URL        |
| `start` | `number` | ❌        | `>= 0`                   |
| `end`   | `number` | ❌        | `> 0`, `> start`         |
| `speed` | `number` | ❌        | `0.5–4.0`, default `1.0` |

**Response `202`:** Song object with `status: "pending"`.

| Status | Meaning                     |
| ------ | --------------------------- |
| `202`  | Accepted, processing queued |
| `422`  | Validation error            |

**Typical flow:** poll `GET /songs/{id}` until `status === "done"`, then use `stream_url`.

---

### `GET /songs`

List songs with filtering, sorting, and cursor pagination.

**Query params:**

| Param      | Type                                      | Default      | Description                                                  |
| ---------- | ----------------------------------------- | ------------ | ------------------------------------------------------------ |
| `status`   | `pending \| processing \| done \| failed` | —            | Filter by job status                                         |
| `favorite` | `boolean`                                 | —            | `true` = favorited only, `false` = unfavorited only          |
| `search`   | `string` (1–200 chars)                    | —            | Case-insensitive title match                                 |
| `sort_by`  | `created_at \| title \| duration`         | `created_at` | Sort field                                                   |
| `order`    | `asc \| desc`                             | `desc`       | Sort direction                                               |
| `limit`    | `integer` (1–1000)                        | `50`         | Records per page                                             |
| `after`    | `UUID`                                    | —            | Cursor for next page (use `bookmark` from previous response) |

**Response `200`:** Paginated list. `count` = total matching records before pagination.

```bash
# Done songs, newest first
GET /songs?status=done&limit=10

# Next page
GET /songs?status=done&limit=10&after=<bookmark>

# Title search
GET /songs?search=lofi&sort_by=title&order=asc

# Favorites only
GET /songs?favorite=true
```

---

### `GET /songs/{id}`

Get a single song by ID.

**Response `200`:** Song object.

| Status | Meaning                   |
| ------ | ------------------------- |
| `200`  | Song found                |
| `404`  | Not found or soft-deleted |

---

### `DELETE /songs/{id}`

Soft-delete a song. Also removes the file from MinIO.

**Response `204`:** No body.

| Status | Meaning                      |
| ------ | ---------------------------- |
| `204`  | Deleted                      |
| `404`  | Not found or already deleted |

---

### `GET /songs/{id}/stream`

Stream the mp3. Trim and speed are applied on-the-fly via FFmpeg — no pre-processing needed.

**Response `200`:** `audio/mpeg` binary stream with `Content-Disposition: attachment; filename="<title>.mp3"`.

| Status | Meaning                            |
| ------ | ---------------------------------- |
| `200`  | Stream started                     |
| `404`  | Song not found                     |
| `409`  | Song not ready (`status != done`)  |
| `500`  | Song is done but has no `file_url` |
| `502`  | MinIO fetch or FFmpeg error        |

**Stream pipeline by case:**

| `start/end` set? | `speed != 1.0`? | Behavior                       |
| ---------------- | --------------- | ------------------------------ |
| ❌                | ❌               | Direct MinIO proxy (fastest)   |
| ✅                | ❌               | Fetch → FFmpeg trim → stream   |
| ❌                | ✅               | Fetch → FFmpeg atempo → stream |
| ✅                | ✅               | Fetch → trim → atempo → stream |

To play inline in the browser: `<audio src="/songs/{id}/stream" controls>`

---

## Favorites

### `POST /favorites/{song_id}`

Mark a song as favorite. Idempotent.

**Response:** Song id confirmation.

| Status | Meaning           |
| ------ | ----------------- |
| `201`  | Newly favorited   |
| `200`  | Already favorited |
| `404`  | Song not found    |

---

### `DELETE /favorites/{song_id}`

Remove a song from favorites (soft-delete).

**Response `204`:** No body.

| Status | Meaning                         |
| ------ | ------------------------------- |
| `204`  | Removed                         |
| `404`  | Song not found or not favorited |

---

### `GET /favorites`

List all favorited songs, ordered by when they were favorited (newest first).

**Response `200`:**
```json
{
  "body": {
    "records": [ ...song objects with is_favorite: true ],
    "count": 5,
    "bookmark": null
  }
}
```

> Note: `bookmark` is always `null` here — no cursor pagination on this endpoint yet.

---

## Playlists

### Playlist Object

```json
{
  "id": "019487ab-...",
  "name": "Morning Mix",
  "created_at": "2024-01-15T10:30:00.000000",
  "song_count": 3
}
```

Playlist detail (from `GET /playlists/{id}`) adds `songs` array (full song objects ordered by position) and omits `song_count`.

---

### `POST /playlists`

Create a playlist.

**Request body:**
```json
{ "name": "Morning Mix" }
```

| Field  | Constraint               |
| ------ | ------------------------ |
| `name` | Non-empty, max 255 chars |

**Response `201`:** Playlist object with `song_count: 0`.

---

### `GET /playlists`

List all playlists, newest first.

**Response `200`:** Paginated list of playlist objects (with `song_count`). `bookmark` always `null` (no cursor pagination).

---

### `GET /playlists/{id}`

Get playlist detail including ordered songs.

**Response `200`:**
```json
{
  "body": {
    "id": "...",
    "name": "Morning Mix",
    "created_at": "...",
    "songs": [ ...song objects in position order ]
  }
}
```

| Status | Meaning   |
| ------ | --------- |
| `200`  | Found     |
| `404`  | Not found |

---

### `DELETE /playlists/{id}`

Soft-delete a playlist. Song associations are preserved in DB.

**Response `204`:** No body.

| Status | Meaning   |
| ------ | --------- |
| `204`  | Deleted   |
| `404`  | Not found |

---

### `POST /playlists/{id}/songs/{song_id}`

Add a song to a playlist. Appended at the end (auto-position). Idempotent.

**Response:**

| Status | Meaning                                             |
| ------ | --------------------------------------------------- |
| `201`  | Added                                               |
| `200`  | Already in playlist                                 |
| `404`  | Playlist or song not found                          |
| `409`  | Position conflict after retries (retry the request) |

---

### `DELETE /playlists/{id}/songs/{song_id}`

Remove a song from a playlist (hard-delete join row).

**Response `204`:** No body.

| Status | Meaning                                 |
| ------ | --------------------------------------- |
| `204`  | Removed                                 |
| `404`  | Playlist, song, or membership not found |

---

## Health

### `GET /health`

Probe all infrastructure dependencies.

**Response `200`:**
```json
{
  "body": {
    "db": "ok",
    "redis": "ok",
    "minio": "ok"
  }
}
```

Any value other than `"ok"` means that service is degraded.

---

## Error Responses

All errors follow the envelope shape:

```json
{
  "status_code": 404,
  "message": "Not found.",
  "body": { "detail": "Song 019487ab-... not found." }
}
```

FastAPI validation errors (`422`) include a `detail` array with per-field info.

---

## Frontend Integration Notes

### Polling for job completion

```javascript
async function waitForSong(id, intervalMs = 2000, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(`/songs/${id}`);
    const { body } = await res.json();
    if (body.status === 'done') return body;
    if (body.status === 'failed') throw new Error('Processing failed');
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error('Timeout waiting for song');
}
```

### Audio playback

```html
<!-- Simple player -->
<audio src="/songs/{id}/stream" controls preload="none"></audio>
```

```javascript
// Programmatic
const audio = new Audio(`/songs/${id}/stream`);
audio.play();
```

### Pagination

```javascript
async function fetchAllSongs(params = {}) {
  const results = [];
  let bookmark = null;
  do {
    const qs = new URLSearchParams({ limit: 50, ...params });
    if (bookmark) qs.set('after', bookmark);
    const { body } = await fetch(`/songs?${qs}`).then(r => r.json());
    results.push(...body.records);
    bookmark = body.bookmark;
  } while (bookmark);
  return results;
}
```

### Song status flow

```
pending → processing → done   → stream_url = /songs/{id}/stream
                     → failed → show error, allow retry via POST /songs
```

While `status` is `pending` or `processing`, `stream_url` points to `GET /songs/{id}` (the status endpoint), not the stream. Always check `status === 'done'` before attempting playback.
