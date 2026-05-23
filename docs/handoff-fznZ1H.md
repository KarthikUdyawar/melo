# Melo — Handoff Document

**Project:** Melo (self-hosted personal audio library)
**Sprint:** 3 (wrapping up) → Sprint 4 prep
**Stack:** FastAPI · yt-dlp · FFmpeg · MinIO · PostgreSQL · Redis + Celery · Docker · uv
**PRD:** `docs/PRD.md` | **Sprint board:** `docs/sprints/Sprint-3.md`

---

## What Was Done This Session

### API-2 — Filtering, Sorting & Search (`GET /songs`)

Implemented and tested cursor-based pagination + filtering on `GET /songs`.

#### Files changed / created

| File                                            | Change                                                                                                                                                                                      |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/core/uuid7.py`                             | **NEW then DELETED** — hand-rolled UUID v7. User chose `uuid6` pip package instead. **Delete this file if it exists.**                                                                      |
| `app/models/song.py`                            | `default=uuid7` (from `uuid6`), `index=True` on `status` + `created_at`, btree index on `title`                                                                                             |
| `app/models/favorite.py`                        | `default=uuid7` (from `uuid6`) replacing `uuid.uuid4`                                                                                                                                       |
| `app/models/playlist.py`                        | `default=uuid7` (from `uuid6`) on all PKs                                                                                                                                                   |
| `app/api/songs.py`                              | `list_songs` full rewrite with filters + cursor pagination. `SortBy`/`SortOrder` StrEnums. mypy fixes: `ColumnElement[Any]` return types, docstrings on enums + `build_content_disposition` |
| `app/api/responses.py`                          | `paginated_response` gains `bookmark` kwarg (default `None`)                                                                                                                                |
| `tests/integration/test_songs_api_filtering.py` | **NEW** — 23 tests, 5 TDD slices                                                                                                                                                            |
| `tests/smoke_test.sh`                           | S20–S24 added. Summary: 19 → 24 sections                                                                                                                                                    |

#### pyproject.toml — add dependency

```toml
"uuid6>=2025.0.1",
```

Run: `uv add uuid6`

#### Key design decisions

- **UUID v7** via `uuid6` package. All model PKs. String-sortable = chronological = natural cursor key.
- **Cursor pagination**: `after=<uuid>` param. Looks up anchor row, then `col > anchor_val` (asc) or `col < anchor_val` (desc).
- **`count`** = total matching before pagination. **`bookmark`** = last record's `id`, or `null`.
- **Cursor tie-breaking** on `title`/`duration` not implemented — deferred to API-3 (add secondary sort on `id`).

---

## Sprint-3 Status

| Ticket                               | Status              |
| ------------------------------------ | ------------------- |
| FFMPEG-2, DX-2, DX-3, DX-4, DX-5     | ✅                   |
| META-2, LIB-1, LIB-2                 | ✅                   |
| **API-2**                            | ✅ done this session |
| API-3 — Computed fields & UX polish  | ⬜ not started       |
| DX-1 — `make seed`, `make clean-tmp` | 🔶 partial           |

Sprint-3 DoD blockers:
- [ ] Run integration tests (`make test-integration`)
- [ ] All branches merged into `develop`
- [ ] `Sprint-3.md` moved to `melo/docs/sprints/`

---

## Next Up — API-3

```python
effective_duration = (end - start) if start and end else duration
upload_date: "YYYYMMDD" → "YYYY-MM-DD"
stream_url: str  # pre-signed or local route
```

DX-1 remainders: `make seed`, `make clean-tmp`

---

## Gotchas

- `/songs/preview` must stay before `/{song_id}` in router (FastAPI route ordering).
- Patch `app.services.downloader.probe_metadata` at source, not import site.
- Unit test isolation via `_truncate_all()` — savepoint unreliable when endpoint calls `db.commit()`.
- `app/core/uuid7.py` — delete if present, superseded by `uuid6` package.
- No Alembic — schema changes applied via `init_db()` or manually.

---

## Suggested Skills

- `/caveman ultra`
- `/tdd`
- `/clean-code`
