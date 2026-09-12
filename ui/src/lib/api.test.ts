import { http, HttpResponse } from "msw";
import { server } from "@/test/server";
import * as api from "./api";
import { ApiError } from "./types";

describe("previewSong", () => {
    it("unwraps envelope body on 200", async () => {
        server.use(
            http.post("/api/songs/preview", () =>
                HttpResponse.json({
                    status_code: 200,
                    message: "ok",
                    body: {
                        youtube_id: "dQw4w9WgXcQ",
                        title: "Never Gonna Give You Up",
                        duration: 213,
                        thumbnail_url: "https://example.com/thumb.jpg",
                        channel: "RickAstleyVEVO",
                        upload_date: "2009-10-25",
                    },
                })
            )
        );

        const result = await api.previewSong("https://youtube.com/watch?v=dQw4w9WgXcQ");
        expect(result.youtube_id).toBe("dQw4w9WgXcQ");
        expect(result.title).toBe("Never Gonna Give You Up");
    });

    it("throws ApiError with envelope message on 422", async () => {
        server.use(
            http.post("/api/songs/preview", () =>
                HttpResponse.json(
                    { status_code: 422, message: "Invalid YouTube URL.", body: { detail: [] } },
                    { status: 422 }
                )
            )
        );

        await expect(api.previewSong("not-a-url")).rejects.toMatchObject({
            message: "Invalid YouTube URL.",
            status: 422,
        });
    });

    it("throws ApiError instance, not a plain object", async () => {
        server.use(
            http.post("/api/songs/preview", () =>
                HttpResponse.json({ status_code: 502, message: "yt-dlp fetch failed", body: {} }, { status: 502 })
            )
        );

        await expect(api.previewSong("x")).rejects.toBeInstanceOf(ApiError);
    });
});

describe("submitSong", () => {
    it("posts trim/speed params and returns the pending song", async () => {
        server.use(
            http.post("/api/songs", async ({ request }) => {
                const body = await request.json();
                expect(body).toEqual({ url: "https://youtube.com/watch?v=x", start: 10, speed: 1.5 });
                return HttpResponse.json(
                    { status_code: 202, message: "Accepted", body: { id: "1", status: "pending" } },
                    { status: 202 }
                );
            })
        );

        const result = await api.submitSong({
            url: "https://youtube.com/watch?v=x",
            start: 10,
            speed: 1.5,
        });
        expect(result.status).toBe("pending");
    });
});

describe("listSongs", () => {
    it("serializes params into a query string", async () => {
        server.use(
            http.get("/api/songs", ({ request }) => {
                const url = new URL(request.url);
                expect(url.searchParams.get("status")).toBe("done");
                expect(url.searchParams.get("limit")).toBe("10");
                return HttpResponse.json({
                    status_code: 200,
                    message: "ok",
                    body: { records: [], count: 0, bookmark: null },
                });
            })
        );

        await api.listSongs({ status: "done", limit: "10" });
    });

    it("omits the query string entirely with no params", async () => {
        server.use(
            http.get("/api/songs", ({ request }) => {
                expect(new URL(request.url).search).toBe("");
                return HttpResponse.json({
                    status_code: 200,
                    message: "ok",
                    body: { records: [], count: 0, bookmark: null },
                });
            })
        );

        await api.listSongs();
    });
});

describe("deleteSong", () => {
    it("returns undefined on 204 with no body", async () => {
        server.use(http.delete("/api/songs/:id", () => new HttpResponse(null, { status: 204 })));
        const result = await api.deleteSong("abc");
        expect(result).toBeUndefined();
    });
});

describe("favorites", () => {
    it("addFavorite posts to /favorites/:songId", async () => {
        server.use(
            http.post("/api/favorites/:songId", ({ params }) => {
                expect(params.songId).toBe("s1");
                return HttpResponse.json(
                    { status_code: 201, message: "Newly favorited.", body: { id: "s1" } },
                    { status: 201 }
                );
            })
        );
        await api.addFavorite("s1");
    });

    it("removeFavorite returns undefined on 204", async () => {
        server.use(http.delete("/api/favorites/:songId", () => new HttpResponse(null, { status: 204 })));
        await expect(api.removeFavorite("s1")).resolves.toBeUndefined();
    });
});

describe("reorderSongInPlaylist", () => {
    it("PATCHes position and returns updated playlist detail", async () => {
        server.use(
            http.patch("/api/playlists/:playlistId/songs/:songId", async ({ request }) => {
                expect(await request.json()).toEqual({ position: 2 });
                return HttpResponse.json({
                    status_code: 200,
                    message: "Reordered",
                    body: { id: "p1", name: "Mix", created_at: "now", songs: [] },
                });
            })
        );

        const result = await api.reorderSongInPlaylist("p1", "s1", 2);
        expect(result.id).toBe("p1");
    });

    it("throws 422 for out-of-range position", async () => {
        server.use(
            http.patch(
                "/api/playlists/:playlistId/songs/:songId",
                () => HttpResponse.json({ status_code: 422, message: "position out of range", body: {} }, { status: 422 })
            )
        );

        await expect(api.reorderSongInPlaylist("p1", "s1", 99)).rejects.toMatchObject({ status: 422 });
    });
});

describe("checkHealth", () => {
    it("uses the baseline handler from test/handlers.ts", async () => {
        const result = await api.checkHealth();
        expect(result.status).toBe("ok");
    });
});