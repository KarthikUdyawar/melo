import { http, HttpResponse } from "msw";

// Baseline happy-path handlers, matching API_DOC.md's envelope shape.
// Extend per-test with server.use() for 4xx/5xx/edge cases.
export const handlers = [
    http.get("/api/health", () =>
        HttpResponse.json({ status_code: 200, message: "ok", body: { status: "ok", db: "up", redis: "up", minio: "up", env: "test" } })
    ),

    // Baseline empty-list handlers — individual tests override with
    // server.use() for specific data/error cases, per test file.
    http.get("/api/songs", () =>
        HttpResponse.json({ status_code: 200, message: "ok", body: { records: [], count: 0, bookmark: null } })
    ),
    http.get("/api/favorites", () =>
        HttpResponse.json({ status_code: 200, message: "ok", body: { records: [], count: 0, bookmark: null } })
    ),
    http.get("/api/playlists", () =>
        HttpResponse.json({ status_code: 200, message: "ok", body: { records: [], count: 0, bookmark: null } })
    ),
];