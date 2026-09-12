// Types ported from API_DOC.md's Song/Playlist/Envelope shapes.
// Kept as plain interfaces — no runtime validation (zod etc.) added;
// the API is the source of truth and this is a solo trusted backend.

export type SongStatus = "pending" | "processing" | "done" | "failed";

export interface Song {
    id: string;
    title: string | null;
    youtube_id: string | null;
    file_url: string | null;
    duration: number | null;
    start: number | null;
    end: number | null;
    speed: number;
    status: SongStatus;
    thumbnail_url: string | null;
    channel: string | null;
    upload_date: string | null;
    created_at: string;
    is_favorite: boolean;
    stream_url: string;
    effective_duration: number | null;
}

export interface SongPreview {
    youtube_id: string;
    title: string;
    duration: number;
    thumbnail_url: string;
    channel: string;
    upload_date: string;
}

export interface SubmitSongParams {
    url: string;
    start?: number;
    end?: number;
    speed?: number;
}

export interface Playlist {
    id: string;
    name: string;
    created_at: string;
    song_count: number;
}

export interface PlaylistDetail {
    id: string;
    name: string;
    created_at: string;
    songs: Song[];
}

export interface HealthStatus {
    status: "ok" | "degraded";
    db: "up" | "down";
    redis: "up" | "down";
    minio: "up" | "down";
    env: string;
}

export interface PaginatedBody<T> {
    records: T[];
    count: number;
    bookmark: string | null;
}

export interface Envelope<T> {
    status_code: number;
    message: string;
    body: T;
}

/** Thrown by apiFetch on any non-2xx response. */
export class ApiError extends Error {
    constructor(message: string, public status: number) {
        super(message);
        this.name = "ApiError";
    }
}