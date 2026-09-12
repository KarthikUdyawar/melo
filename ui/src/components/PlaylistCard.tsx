import type { Playlist } from "@/lib/types";

/** 1:1 port of components.js's renderPlaylistCard(). */
export function PlaylistCard({
  playlist,
  onOpen,
  onDelete,
}: {
  playlist: Playlist;
  onOpen: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="playlist-card" role="listitem" onClick={onOpen}>
      <div className="playlist-card__name">{playlist.name}</div>
      <div className="playlist-card__meta">
        {playlist.song_count} song{playlist.song_count !== 1 ? "s" : ""}
      </div>
      <button
        className="icon-btn icon-btn--danger"
        aria-label="Delete playlist"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        ✕
      </button>
    </div>
  );
}