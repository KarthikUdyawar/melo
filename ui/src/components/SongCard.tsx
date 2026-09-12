import Image from "next/image";
import type { Song } from "@/lib/types";
import { formatDuration } from "@/lib/format";
import { StatusPill } from "./StatusPill";
import { SongCardMenu } from "./SongCardMenu";

/** 1:1 port of components.js's renderSongCard(). */
export function SongCard({
  song,
  isActive,
  playlistNames,
  onPlay,
  onToggleFavorite,
  onAddToPlaylist,
  onNewPlaylist,
  onDelete,
  onRetry,
}: {
  song: Song;
  isActive: boolean;
  playlistNames: string[];
  onPlay: () => void;
  onToggleFavorite: () => void;
  onAddToPlaylist: (name: string) => void;
  onNewPlaylist: () => void;
  onDelete: () => void;
  onRetry: () => void;
}) {
  const isPlayable = song.status === "done";
  const heartLabel = song.is_favorite ? "Remove from favorites" : "Add to favorites";

  return (
    <div
      className={`song-card${isActive ? " song-card--active" : ""}`}
      role="listitem"
      onClick={() => isPlayable && onPlay()}
    >
      <Image
        className="song-card__thumb"
        src={song.thumbnail_url ?? ""}
        alt={song.title ?? ""}
        width={48}
        height={48}
        unoptimized
        loading="lazy"
        onError={(e) => {
          (e.target as HTMLImageElement).style.visibility = "hidden";
        }}
      />
      <div className="song-card__body">
        <div className="song-card__title">{song.title ?? "Processing…"}</div>
        <div className="song-card__meta">
          <span>{song.channel ?? ""}</span>
          {song.upload_date && (
            <>
              <span>·</span>
              <span>{song.upload_date}</span>
            </>
          )}
          <StatusPill status={song.status} />
          {song.status === "failed" && (
            <button
              className="btn btn--retry"
              aria-label="Retry processing"
              onClick={(e) => {
                e.stopPropagation();
                onRetry();
              }}
            >
              ↺ Retry
            </button>
          )}
        </div>
      </div>
      <div className="song-card__actions" onClick={(e) => e.stopPropagation()}>
        <span className="song-card__duration">
          {formatDuration(song.effective_duration ?? song.duration)}
        </span>
        <button
          className={`icon-btn${song.is_favorite ? " icon-btn--active" : ""}`}
          aria-label={heartLabel}
          onClick={onToggleFavorite}
        >
          {heartSvg(song.is_favorite)}
        </button>
        <SongCardMenu
          playlistNames={playlistNames}
          onAddToPlaylist={onAddToPlaylist}
          onNewPlaylist={onNewPlaylist}
          onDelete={onDelete}
        />
      </div>
    </div>
  );
}

function heartSvg(filled: boolean) {
  return filled ? (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="var(--danger)">
      <path d="M10 17s-7-4.35-7-9a4 4 0 0 1 7-2.65A4 4 0 0 1 17 8c0 4.65-7 9-7 9z" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path d="M10 17s-7-4.35-7-9a4 4 0 0 1 7-2.65A4 4 0 0 1 17 8c0 4.65-7 9-7 9z" />
    </svg>
  );
}