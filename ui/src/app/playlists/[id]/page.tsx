"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { PlaylistDetail } from "@/lib/types";
import { SongCard } from "@/components/SongCard";
import { useToast } from "@/components/Toast";
import { parsePlaylistId } from "@/lib/playlist-path";

/**
 * Static export needs a build-time-known param; the real id is unknown
 * until runtime, so this shell is the only page emitted. nginx rewrites
 * any real /playlists/<uuid>/ request to this shell's index.html — see
 * next.config.mjs's `output: 'export'` and DECISIONS.md Sprint 7.
 */
export function generateStaticParams() {
  return [{ id: "_" }];
}

/** Drag-reorder is FE7-7 — read-only ordered list for now. */
export default function PlaylistDetailPage() {
  const { show } = useToast();
  const [playlist, setPlaylist] = useState<PlaylistDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    const id = parsePlaylistId(window.location.pathname);
    if (!id) {
      setNotFound(true);
      return;
    }
    api
      .getPlaylist(id)
      .then(setPlaylist)
      .catch(() => setNotFound(true));
  }, []);

  const onRemove = async (songId: string) => {
    if (!playlist) return;
    try {
      await api.removeSongFromPlaylist(playlist.id, songId);
      show("Removed from playlist");
      const refreshed = await api.getPlaylist(playlist.id);
      setPlaylist(refreshed);
    } catch (err) {
      show((err as Error).message, "error");
    }
  };

  if (notFound) {
    return (
      <div className="empty-state">
        <span className="empty-state__label">Playlist not found.</span>
        <Link className="btn btn--ghost" href="/playlists/">Back</Link>
      </div>
    );
  }

  if (!playlist) return null;

  return (
    <>
      <Link className="back-link" href="/playlists/">← Playlists</Link>
      <div className="page-header">
        <h1 className="page-title">{playlist.name}</h1>
      </div>
      {playlist.songs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__label">No songs in playlist.</span>
        </div>
      ) : (
        <div className="song-list" role="list">
          {playlist.songs.map((song, i) => (
            <div className="playlist-song-row" key={song.id}>
              <span className="playlist-song-row__pos">{i + 1}</span>
              <SongCard
                song={song}
                isActive={false}
                playlistNames={[]}
                onPlay={() => {}}
                onToggleFavorite={() => {}}
                onAddToPlaylist={() => {}}
                onNewPlaylist={() => {}}
                onDelete={() => {}}
                onRetry={() => {}}
              />
              <button
                className="icon-btn"
                aria-label="Remove from playlist"
                onClick={() => onRemove(song.id)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}