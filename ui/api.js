/** @param {string} path @param {RequestInit} init */
async function apiFetch(path, init = {}) {
    const res = await fetch(`/api${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...init.headers },
    });
    if (res.status === 204) return undefined;
    const envelope = await res.json();
    if (!res.ok) throw new Error(envelope.message ?? res.statusText);
    return envelope.body;
}

// ── Songs ────────────────────────────────────────────────────────────────

/** @param {string} url */
export function previewSong(url) {
    return apiFetch('/songs/preview', {
        method: 'POST',
        body: JSON.stringify({ url }),
    });
}

/** @param {{ url: string, start?: number, end?: number, speed?: number }} params */
export function submitSong(params) {
    return apiFetch('/songs', {
        method: 'POST',
        body: JSON.stringify(params),
    });
}

/** @param {Record<string, string>} params */
export function listSongs(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return apiFetch(`/songs${qs ? `?${qs}` : ''}`);
}

/** @param {string} id */
export function getSong(id) {
    return apiFetch(`/songs/${id}`);
}

/** @param {string} id */
export function deleteSong(id) {
    return apiFetch(`/songs/${id}`, { method: 'DELETE' });
}

// ── Favorites ────────────────────────────────────────────────────────────

/** @param {string} songId */
export function addFavorite(songId) {
    return apiFetch(`/favorites/${songId}`, { method: 'POST' });
}

/** @param {string} songId */
export function removeFavorite(songId) {
    return apiFetch(`/favorites/${songId}`, { method: 'DELETE' });
}

export function listFavorites() {
    return apiFetch('/favorites');
}

// ── Playlists ────────────────────────────────────────────────────────────

/** @param {string} name */
export function createPlaylist(name) {
    return apiFetch('/playlists', {
        method: 'POST',
        body: JSON.stringify({ name }),
    });
}

export function listPlaylists() {
    return apiFetch('/playlists');
}

/** @param {string} id */
export function getPlaylist(id) {
    return apiFetch(`/playlists/${id}`);
}

/** @param {string} id */
export function deletePlaylist(id) {
    return apiFetch(`/playlists/${id}`, { method: 'DELETE' });
}

/** @param {string} playlistId @param {string} songId */
export function addSongToPlaylist(playlistId, songId) {
    return apiFetch(`/playlists/${playlistId}/songs/${songId}`, { method: 'POST' });
}

/** @param {string} playlistId @param {string} songId */
export function removeSongFromPlaylist(playlistId, songId) {
    return apiFetch(`/playlists/${playlistId}/songs/${songId}`, { method: 'DELETE' });
}

// ── Health ───────────────────────────────────────────────────────────────

export function checkHealth() {
    return apiFetch('/health');
}
