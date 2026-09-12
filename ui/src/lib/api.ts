// Ported from ui/api.js's apiFetch() — same envelope-unwrap and
// error-shape behavior, now typed against API_DOC.md.

import {
    ApiError,
    type Envelope,
    type HealthStatus,
    type PaginatedBody,
    type Playlist,
    type PlaylistDetail,
    type Song,
    type SongPreview,
    type SubmitSongParams,
} from "./types";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetch(`/api${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init.headers },
    });

    if (res.status === 204) return undefined as T;

    const isJson = (res.headers.get("content-type") ?? "").includes("application/json");
    const payload = isJson ? await res.json() : await res.text();

    if (!res.ok) {
        const message =
            typeof payload === "object" && payload !== null
                ? (payload as Envelope<unknown>).message ?? res.statusText
                : (payload as string) || res.statusText;
        throw new ApiError(message, res.status);
    }

    return typeof payload === "object" && payload !== null
        ? (payload as Envelope<T>).body
        : (payload as T);
}

// ── Songs ────────────────────────────────────────────────────────────────

export function previewSong(url: string): Promise<SongPreview> {
    return apiFetch("/songs/preview", { method: "POST", body: JSON.stringify({ url }) });
}

export function submitSong(params: SubmitSongParams): Promise<Song> {
    return apiFetch("/songs", { method: "POST", body: JSON.stringify(params) });
}

export function listSongs(
    params: Record<string, string> = {}
): Promise<PaginatedBody<Song>> {
    const qs = new URLSearchParams(params).toString();
    return apiFetch(`/songs${qs ? `?${qs}` : ""}`);
}

export function getSong(id: string): Promise<Song> {
    return apiFetch(`/songs/${id}`);
}

export function deleteSong(id: string): Promise<void> {
    return apiFetch(`/songs/${id}`, { method: "DELETE" });
}

// ── Favorites ────────────────────────────────────────────────────────────

export function addFavorite(songId: string): Promise<{ id: string }> {
    return apiFetch(`/favorites/${songId}`, { method: "POST" });
}

export function removeFavorite(songId: string): Promise<void> {
    return apiFetch(`/favorites/${songId}`, { method: "DELETE" });
}

export function listFavorites(): Promise<PaginatedBody<Song>> {
    return apiFetch("/favorites");
}

// ── Playlists ────────────────────────────────────────────────────────────

export function createPlaylist(name: string): Promise<Playlist> {
    return apiFetch("/playlists", { method: "POST", body: JSON.stringify({ name }) });
}

export function listPlaylists(): Promise<PaginatedBody<Playlist>> {
    return apiFetch("/playlists");
}

export function getPlaylist(id: string): Promise<PlaylistDetail> {
    return apiFetch(`/playlists/${id}`);
}

export function deletePlaylist(id: string): Promise<void> {
    return apiFetch(`/playlists/${id}`, { method: "DELETE" });
}

export function addSongToPlaylist(playlistId: string, songId: string): Promise<{ id: string }> {
    return apiFetch(`/playlists/${playlistId}/songs/${songId}`, { method: "POST" });
}

export function removeSongFromPlaylist(playlistId: string, songId: string): Promise<void> {
    return apiFetch(`/playlists/${playlistId}/songs/${songId}`, { method: "DELETE" });
}

export function reorderSongInPlaylist(
    playlistId: string,
    songId: string,
    position: number
): Promise<PlaylistDetail> {
    return apiFetch(`/playlists/${playlistId}/songs/${songId}`, {
        method: "PATCH",
        body: JSON.stringify({ position }),
    });
}

// ── Health ───────────────────────────────────────────────────────────────

export function checkHealth(): Promise<HealthStatus> {
    return apiFetch("/health");
}