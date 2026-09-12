"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Ported from renderSongCard()'s inline dropdown markup in components.js.
 * Plain native <button>s, no role="menu"/"menuitem" — no keyboard model
 * backs those roles (post-Sprint-6 CodeRabbit fix, see DECISIONS.md).
 */
export function SongCardMenu({
  playlistNames,
  onAddToPlaylist,
  onNewPlaylist,
  onDelete,
}: {
  playlistNames: string[];
  onAddToPlaylist: (name: string) => void;
  onNewPlaylist: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onOutside = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onOutside);
    return () => document.removeEventListener("click", onOutside);
  }, [open]);

  return (
    <div className="dropdown" ref={ref}>
      <button
        className="icon-btn"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="More options"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
      >
        {moreIcon()}
      </button>
      {open && (
        <div className="dropdown__menu">
          {playlistNames.map((n) => (
            <button
              key={n}
              className="dropdown__item"
              onClick={() => {
                onAddToPlaylist(n);
                setOpen(false);
              }}
            >
              {n}
            </button>
          ))}
          <button
            className="dropdown__item"
            onClick={() => {
              onNewPlaylist();
              setOpen(false);
            }}
          >
            + New playlist
          </button>
          <div className="dropdown__divider" />
          <button
            className="dropdown__item dropdown__item--danger"
            onClick={() => {
              onDelete();
              setOpen(false);
            }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function moreIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
      <circle cx="10" cy="4" r="1.5" />
      <circle cx="10" cy="10" r="1.5" />
      <circle cx="10" cy="16" r="1.5" />
    </svg>
  );
}