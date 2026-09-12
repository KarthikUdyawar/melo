"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { Playlist } from "@/lib/types";
import { PlaylistCard } from "@/components/PlaylistCard";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";

export default function PlaylistsPage() {
  const { show } = useToast();
  const router = useRouter();
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [showNewInput, setShowNewInput] = useState(false);
  const [newName, setNewName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const refresh = () =>
    api.listPlaylists().then((d) => setPlaylists(d.records)).catch((err) => show(err.message, "error"));

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      await api.createPlaylist(name);
      setNewName("");
      setShowNewInput(false);
      await refresh();
      show(`Playlist "${name}" created`);
    } catch (err) {
      show((err as Error).message, "error");
    }
  };

  const onDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.deletePlaylist(deleteTarget);
      show("Playlist deleted");
      await refresh();
    } catch (err) {
      show((err as Error).message, "error");
    } finally {
      setDeleteTarget(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Playlists</h1>
        <button className="btn btn--ghost" onClick={() => setShowNewInput(true)}>
          + New Playlist
        </button>
      </div>
      {showNewInput && (
        <div className="inline-input-wrap">
          <input
            className="filter-input"
            placeholder="Playlist name…"
            maxLength={255}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onCreate();
              if (e.key === "Escape") setShowNewInput(false);
            }}
            autoFocus
          />
          <button className="btn btn--accent" onClick={onCreate}>Create</button>
          <button className="btn btn--ghost" onClick={() => setShowNewInput(false)}>Cancel</button>
        </div>
      )}
      {playlists.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__label">No playlists yet.</span>
        </div>
      ) : (
        <div className="playlist-grid" role="list">
          {playlists.map((p) => (
            <PlaylistCard
              key={p.id}
              playlist={p}
              onOpen={() => router.push(`/playlists/${p.id}/`)}
              onDelete={() => setDeleteTarget(p.id)}
            />
          ))}
        </div>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title="Delete Playlist"
          message="Delete this playlist? This cannot be undone."
          onConfirm={onDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}