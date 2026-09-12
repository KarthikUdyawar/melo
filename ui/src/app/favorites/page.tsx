"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Song } from "@/lib/types";
import { SongCard } from "@/components/SongCard";
import { useToast } from "@/components/Toast";

export default function FavoritesPage() {
  const { show } = useToast();
  const [songs, setSongs] = useState<Song[]>([]);

  useEffect(() => {
    api.listFavorites().then((d) => setSongs(d.records)).catch((err) => show(err.message, "error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onToggleFavorite = async (song: Song) => {
    try {
      await api.removeFavorite(song.id);
      setSongs((prev) => prev.filter((s) => s.id !== song.id));
    } catch (err) {
      show((err as Error).message, "error");
    }
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Favorites</h1>
      </div>
      {songs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__label">No favorites yet.</span>
        </div>
      ) : (
        <div className="song-list" role="list">
          {songs.map((song) => (
            <SongCard
              key={song.id}
              song={song}
              isActive={false}
              playlistNames={[]}
              onPlay={() => {}}
              onToggleFavorite={() => onToggleFavorite(song)}
              onAddToPlaylist={() => {}}
              onNewPlaylist={() => {}}
              onDelete={() => {}}
              onRetry={() => {}}
            />
          ))}
        </div>
      )}
    </>
  );
}