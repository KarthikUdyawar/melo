"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import type { Song, Playlist } from "@/lib/types";
import { SongCard } from "@/components/SongCard";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { hasMorePages } from "@/lib/pagination";

const LIMIT = 50;

/** Ported from app.js's Library page: filter/search/sort, 2s poll while
 *  any song is pending/processing, cursor pagination via bookmark. */
export default function LibraryPage() {
  const { show } = useToast();
  const [songs, setSongs] = useState<Song[]>([]);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("created_at|desc");
  const [bookmark, setBookmark] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.listPlaylists().then((d) => setPlaylists(d.records)).catch(() => {});
  }, []);

  const buildParams = useCallback(
    (after?: string) => {
      const [sort_by, order] = sort.split("|");
      const params: Record<string, string> = { sort_by, order, limit: String(LIMIT) };
      if (search) params.search = search;
      if (status) params.status = status;
      if (after) params.after = after;
      return params;
    },
    [search, status, sort]
  );

  const load = useCallback(
    async (append: boolean) => {
      try {
        const data = await api.listSongs(buildParams(append ? bookmark ?? undefined : undefined));
        setSongs((prev) => (append ? [...prev, ...data.records] : data.records));
        setBookmark(hasMorePages(data.bookmark, data.records.length, LIMIT) ? data.bookmark : null);
      } catch (err) {
        show((err as Error).message, "error");
      }
    },
    [buildParams, bookmark, show]
  );

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status, sort]);

  useEffect(() => {
    const hasPending = songs.some((s) => s.status === "pending" || s.status === "processing");
    if (hasPending && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const data = await api.listSongs(buildParams());
          setSongs(data.records);
        } catch {
          /* transient poll failure, ignore */
        }
      }, 2000);
    } else if (!hasPending && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [songs, buildParams]);

  const patchSong = (id: string, patch: Partial<Song>) =>
    setSongs((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));

  const onToggleFavorite = async (song: Song) => {
    patchSong(song.id, { is_favorite: !song.is_favorite });
    try {
      song.is_favorite ? await api.removeFavorite(song.id) : await api.addFavorite(song.id);
    } catch (err) {
      patchSong(song.id, { is_favorite: song.is_favorite });
      show((err as Error).message, "error");
    }
  };

  const onDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteSong(deleteTarget);
      show("Song deleted");
      setSongs((prev) => prev.filter((s) => s.id !== deleteTarget));
    } catch (err) {
      show((err as Error).message, "error");
    } finally {
      setDeleteTarget(null);
    }
  };

  const onRetry = async (song: Song) => {
    const url = `https://www.youtube.com/watch?v=${song.youtube_id}`;
    const params: Parameters<typeof api.submitSong>[0] = { url };
    if (song.start != null) params.start = song.start;
    if (song.end != null) params.end = song.end;
    if (song.speed && song.speed !== 1.0) params.speed = song.speed;
    try {
      await api.submitSong(params);
      await api.deleteSong(song.id);
      show("Retrying…");
      load(false);
    } catch (err) {
      show((err as Error).message, "error");
    }
  };

  const onAddToPlaylist = async (song: Song, playlistName: string) => {
    const playlist = playlists.find((p) => p.name === playlistName);
    if (!playlist) return;
    try {
      await api.addSongToPlaylist(playlist.id, song.id);
      show(`Added to "${playlistName}"`);
    } catch (err) {
      show((err as Error).message, "error");
    }
  };

  const onNewPlaylist = async (song: Song) => {
    const name = window.prompt("New playlist name:")?.trim();
    if (!name) return;
    try {
      const playlist = await api.createPlaylist(name);
      await api.addSongToPlaylist(playlist.id, song.id);
      setPlaylists((prev) => [...prev, playlist]);
      show(`Added to "${name}"`);
    } catch (err) {
      show((err as Error).message, "error");
    }
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Library</h1>
      </div>
      <div className="filter-bar">
        <input
          className="filter-input"
          placeholder="Search songs…"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="filter-input" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All status</option>
          <option value="done">Done</option>
          <option value="pending">Pending</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
        <select className="filter-input" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="created_at|desc">Newest</option>
          <option value="created_at|asc">Oldest</option>
          <option value="title|asc">Title A–Z</option>
          <option value="duration|desc">Longest</option>
        </select>
      </div>

      {songs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__label">No songs yet.</span>
        </div>
      ) : (
        <div className="song-list" role="list">
          {songs.map((song) => (
            <SongCard
              key={song.id}
              song={song}
              isActive={false}
              playlistNames={playlists.map((p) => p.name)}
              onPlay={() => {
                /* TODO FE7-4: wire to PlayerProvider */
              }}
              onToggleFavorite={() => onToggleFavorite(song)}
              onAddToPlaylist={(name) => onAddToPlaylist(song, name)}
              onNewPlaylist={() => onNewPlaylist(song)}
              onDelete={() => setDeleteTarget(song.id)}
              onRetry={() => onRetry(song)}
            />
          ))}
        </div>
      )}

      {bookmark && (
        <div className="load-more-wrap">
          <button className="btn btn--ghost" onClick={() => load(true)}>
            Load more
          </button>
        </div>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete Song"
          message="Delete this song? This cannot be undone."
          onConfirm={onDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}