"use client";

// ui/src/app/playlists/[id]/PlaylistDetailClient.tsx
// Actual render logic, split out of page.tsx so page.tsx can stay a
// Server Component (generateStaticParams requirement). Reads real
// playlist id from window.location.pathname — see playlist-path.ts.

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import * as api from "@/lib/api";
import type { PlaylistDetail } from "@/lib/types";
import { SongCard } from "@/components/SongCard";
import { usePlayer } from "@/components/PlayerProvider";
import { useToast } from "@/components/Toast";
import { parsePlaylistId } from "@/lib/playlist-path";
import { moveItem } from "@/lib/reorder";

/**
 * FE7-7: native HTML5 drag-and-drop reorder + ArrowUp/ArrowDown keyboard
 * alt, both calling the same optimistic-update + PATCH + resync-on-
 * failure path — ported from app.js's reorderPlaylistSongOptimistic().
 */
export function PlaylistDetailClient() {
  const { show } = useToast();
  const { currentSong, setQueueAndPlay } = usePlayer();
  const [playlist, setPlaylist] = useState<PlaylistDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const dragSongId = useRef<string | null>(null);
  const focusSongId = useRef<string | null>(null);
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map());

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

  // Row is replaced on re-render after a reorder — restore focus so
  // keyboard users don't lose their place (ported from app.js's
  // handlePlaylistRowKeydown requestAnimationFrame refocus).
  useEffect(() => {
    if (!focusSongId.current) return;
    rowRefs.current.get(focusSongId.current)?.focus();
    focusSongId.current = null;
  }, [playlist]);

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

  const reorder = async (songId: string, newPosition: number) => {
    if (!playlist) return;
    const oldIndex = playlist.songs.findIndex((s) => s.id === songId);
    if (oldIndex === -1 || oldIndex === newPosition) return;

    const songs = moveItem(playlist.songs, oldIndex, newPosition);
    setPlaylist({ ...playlist, songs }); // optimistic
    try {
      await api.reorderSongInPlaylist(playlist.id, songId, newPosition);
    } catch (err) {
      show((err as Error).message, "error");
      try {
        setPlaylist(await api.getPlaylist(playlist.id)); // resync
      } catch {
        /* resync fetch failing is already surfaced by the toast above */
      }
    }
  };

  const onRowKeyDown = (
    e: React.KeyboardEvent,
    songId: string,
    position: number,
  ) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    e.preventDefault();
    const newPos = position + (e.key === "ArrowUp" ? -1 : 1);
    if (!playlist || newPos < 0 || newPos >= playlist.songs.length) return; // no-op at boundaries
    focusSongId.current = songId;
    reorder(songId, newPos);
  };

  if (notFound) {
    return (
      <div className="empty-state">
        <span className="empty-state__label">Playlist not found.</span>
        <Link className="btn btn--ghost" href="/playlists/">
          Back
        </Link>
      </div>
    );
  }

  if (!playlist) return null;

  return (
    <>
      <Link className="back-link" href="/playlists/">
        ← Playlists
      </Link>
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
            <div
              className="playlist-song-row"
              key={song.id}
              ref={(el) => {
                if (el) rowRefs.current.set(song.id, el);
                else rowRefs.current.delete(song.id);
              }}
              draggable
              tabIndex={0}
              aria-label={`${song.title ?? "Song"}, position ${i + 1} of ${playlist.songs.length}`}
              onDragStart={() => {
                dragSongId.current = song.id;
              }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => {
                const draggedId = dragSongId.current;
                dragSongId.current = null;
                if (draggedId && draggedId !== song.id) reorder(draggedId, i);
              }}
              onKeyDown={(e) => onRowKeyDown(e, song.id, i)}
            >
              <span className="playlist-song-row__pos">{i + 1}</span>
              <SongCard
                song={song}
                isActive={currentSong?.id === song.id}
                playlistNames={[]}
                onPlay={() => setQueueAndPlay(playlist.songs, song.id)}
                onToggleFavorite={() => {}}
                onAddToPlaylist={() => {}}
                onNewPlaylist={() => {}}
                onDelete={() => {}}
                onRetry={() => {}}
              />
              <span className="sr-only">
                Press Arrow Up or Arrow Down to reorder.
              </span>
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
