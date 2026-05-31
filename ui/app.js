/**
 * app.js — hash router + page renderers + polling + event delegation.
 * Imports from api.js, player.js, components.js.
 */

import * as api from './api.js';
import * as player from './player.js';
import {
    renderSongCard,
    renderPlaylistCard,
    renderStatusPill,
    renderToast,
} from './components.js';

// ── State ─────────────────────────────────────────────────────────────────

const state = {
    pollTimer: null,
    libraryQuery: { sort_by: 'created_at', order: 'desc', limit: '50' },
    bookmark: null,
    playlists: [],          // cache for overflow menu
};

// ── Boot ──────────────────────────────────────────────────────────────────

player.bindScrubber();
bindGlobalEvents();
checkApiHealth();
route();

window.addEventListener('hashchange', () => {
    stopPoll();
    route();
});

// ── Router ────────────────────────────────────────────────────────────────

function route() {
    const hash = window.location.hash || '#/';
    highlightNavLink(hash);

    if (hash === '#/') return renderLibraryPage();
    if (hash === '#/favorites') return renderFavoritesPage();
    if (hash === '#/playlists') return renderPlaylistsPage();

    const playlistMatch = hash.match(/^#\/playlists\/(.+)$/);
    if (playlistMatch) return renderPlaylistDetailPage(playlistMatch[1]);

    renderLibraryPage();
}

function highlightNavLink(hash) {
    document.querySelectorAll('.nav-link').forEach(link => {
        const route = link.dataset.route;
        const active =
            (route === '/' && (hash === '#/' || hash === '#')) ||
            (route !== '/' && hash.startsWith(`#${route}`));
        link.classList.toggle('nav-link--active', active);
    });
}

// ── Library Page ──────────────────────────────────────────────────────────

async function renderLibraryPage() {
    document.title = 'Melo — Library';
    state.bookmark = null;
    const content = document.getElementById('page-content');
    content.innerHTML = buildLibraryShell();
    bindLibraryFilterEvents();
    await loadLibrarySongs(false);
}

function buildLibraryShell() {
    return `
  <div class="page-header">
    <h1 class="page-title">Library</h1>
  </div>
  <div class="filter-bar">
    <input class="filter-input" id="search-input" placeholder="Search songs…" type="search" value="${state.libraryQuery.search ?? ''}" />
    <select class="filter-input" id="status-filter">
      <option value="">All status</option>
      <option value="done">Done</option>
      <option value="pending">Pending</option>
      <option value="processing">Processing</option>
      <option value="failed">Failed</option>
    </select>
    <select class="filter-input" id="sort-select">
      <option value="created_at|desc">Newest</option>
      <option value="created_at|asc">Oldest</option>
      <option value="title|asc">Title A–Z</option>
      <option value="duration|desc">Longest</option>
    </select>
  </div>
  <div class="song-list" id="song-list" role="list"></div>
  <div class="load-more-wrap" id="load-more-wrap" style="display:none">
    <button class="btn btn--ghost" id="btn-load-more">Load more</button>
  </div>`;
}

function bindLibraryFilterEvents() {
    let debounceTimer = null;

    document.getElementById('search-input')?.addEventListener('input', e => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            updateLibraryQuery({ search: e.target.value || undefined, after: undefined });
            state.bookmark = null;
            loadLibrarySongs(false);
        }, 300);
    });

    document.getElementById('status-filter')?.addEventListener('change', e => {
        updateLibraryQuery({ status: e.target.value || undefined, after: undefined });
        state.bookmark = null;
        loadLibrarySongs(false);
    });

    document.getElementById('sort-select')?.addEventListener('change', e => {
        const [sort_by, order] = e.target.value.split('|');
        updateLibraryQuery({ sort_by, order, after: undefined });
        state.bookmark = null;
        loadLibrarySongs(false);
    });

    document.getElementById('btn-load-more')?.addEventListener('click', () => {
        loadLibrarySongs(true);
    });
}

function updateLibraryQuery(patch) {
    Object.assign(state.libraryQuery, patch);
    Object.keys(state.libraryQuery).forEach(k => {
        if (state.libraryQuery[k] === undefined) delete state.libraryQuery[k];
    });
}

async function loadLibrarySongs(append) {
    const params = { ...state.libraryQuery };
    if (state.bookmark) params.after = state.bookmark;

    let data;
    try {
        data = await api.listSongs(params);
    } catch (err) {
        renderToast(err.message, 'error');
        return;
    }

    const list = document.getElementById('song-list');
    if (!list) return;

    const currentSongId = player.getCurrentSongId?.() ?? null;
    const cards = data.records.map(s =>
        renderSongCard(s, s.id === currentSongId, state.playlists.map(p => p.name))
    ).join('');

    if (append) {
        list.insertAdjacentHTML('beforeend', cards);
    } else {
        list.innerHTML = data.records.length === 0 ? buildEmptyLibrary() : cards;
    }

    // Only show "Load more" if the API returned a full page AND there's a bookmark.
    // A partial page means we've reached the end even if bookmark is non-null.
    const limit = parseInt(state.libraryQuery.limit, 10) || 50;
    const hasMore = !!data.bookmark && data.records.length >= limit;
    state.bookmark = hasMore ? data.bookmark : null;

    const loadMoreWrap = document.getElementById('load-more-wrap');
    if (loadMoreWrap) loadMoreWrap.style.display = hasMore ? '' : 'none';

    maybeStartPoll(data.records);
}

function buildEmptyLibrary() {
    return `<div class="empty-state">
    <span class="empty-state__label">No songs yet.</span>
    <button class="btn btn--accent" data-action="open-add-song">Add Song</button>
  </div>`;
}

function maybeStartPoll(songs) {
    const hasPending = songs.some(s => s.status === 'pending' || s.status === 'processing');
    if (hasPending && !state.pollTimer) {
        state.pollTimer = setInterval(() => pollLibrary(), 2000);
    } else if (!hasPending) {
        stopPoll();
    }
}

async function pollLibrary() {
    const params = { ...state.libraryQuery, limit: '50' };
    let data;
    try { data = await api.listSongs(params); } catch { return; }

    const list = document.getElementById('song-list');
    if (!list) { stopPoll(); return; }

    const currentSongId = player.getCurrentSongId?.() ?? null;
    list.innerHTML = data.records.map(s =>
        renderSongCard(s, s.id === currentSongId, state.playlists.map(p => p.name))
    ).join('');

    const stillPending = data.records.some(s => s.status === 'pending' || s.status === 'processing');
    if (!stillPending) stopPoll();
}

function stopPoll() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}

// ── Favorites Page ────────────────────────────────────────────────────────

async function renderFavoritesPage() {
    document.title = 'Melo — Favorites';
    const content = document.getElementById('page-content');
    content.innerHTML = `<div class="page-header"><h1 class="page-title">Favorites</h1></div>
    <div class="song-list" id="song-list" role="list"></div>`;

    let data;
    try { data = await api.listFavorites(); } catch (err) {
        renderToast(err.message, 'error'); return;
    }

    const list = document.getElementById('song-list');
    if (!list) return;

    const currentSongId = player.getCurrentSongId?.() ?? null;
    list.innerHTML = data.records.length === 0
        ? `<div class="empty-state"><span class="empty-state__label">No favorites yet.</span></div>`
        : data.records.map(s =>
            renderSongCard(s, s.id === currentSongId, state.playlists.map(p => p.name))
        ).join('');
}

// ── Playlists Page ────────────────────────────────────────────────────────

async function renderPlaylistsPage() {
    document.title = 'Melo — Playlists';
    const content = document.getElementById('page-content');
    content.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Playlists</h1>
      <button class="btn btn--ghost" id="btn-new-playlist">+ New Playlist</button>
    </div>
    <div id="new-playlist-wrap"></div>
    <div class="playlist-grid" id="playlist-grid" role="list"></div>`;

    document.getElementById('btn-new-playlist')?.addEventListener('click', showNewPlaylistInput);
    await refreshPlaylistGrid();
}

function showNewPlaylistInput() {
    const wrap = document.getElementById('new-playlist-wrap');
    if (!wrap || wrap.querySelector('input')) return;
    wrap.innerHTML = `<div class="inline-input-wrap">
    <input class="filter-input" id="new-playlist-input" placeholder="Playlist name…" maxlength="255" />
    <button class="btn btn--accent" id="btn-create-playlist">Create</button>
    <button class="btn btn--ghost" id="btn-cancel-playlist">Cancel</button>
  </div>`;

    const input = document.getElementById('new-playlist-input');
    input?.focus();

    document.getElementById('btn-cancel-playlist')?.addEventListener('click', () => {
        wrap.innerHTML = '';
    });

    document.getElementById('btn-create-playlist')?.addEventListener('click', () =>
        submitNewPlaylist(input?.value.trim())
    );

    input?.addEventListener('keydown', e => {
        if (e.key === 'Enter') submitNewPlaylist(input.value.trim());
        if (e.key === 'Escape') wrap.innerHTML = '';
    });
}

async function submitNewPlaylist(name) {
    if (!name) return;
    try {
        await api.createPlaylist(name);
        document.getElementById('new-playlist-wrap').innerHTML = '';
        await refreshPlaylistGrid();
        renderToast(`Playlist "${name}" created`);
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

async function refreshPlaylistGrid() {
    let data;
    try { data = await api.listPlaylists(); } catch (err) {
        renderToast(err.message, 'error'); return;
    }
    state.playlists = data.records;
    const grid = document.getElementById('playlist-grid');
    if (!grid) return;
    grid.innerHTML = data.records.length === 0
        ? `<div class="empty-state"><span class="empty-state__label">No playlists yet.</span></div>`
        : data.records.map(renderPlaylistCard).join('');
}

// ── Playlist Detail Page ──────────────────────────────────────────────────

async function renderPlaylistDetailPage(id) {
    document.title = 'Melo — Playlist';
    const content = document.getElementById('page-content');
    content.innerHTML = `<a class="back-link" href="#/playlists">← Playlists</a>
    <div id="playlist-detail-root"></div>`;

    await refreshPlaylistDetail(id);
}

async function refreshPlaylistDetail(id) {
    let playlist;
    try { playlist = await api.getPlaylist(id); } catch {
        document.getElementById('playlist-detail-root').innerHTML =
            `<div class="empty-state"><span class="empty-state__label">Playlist not found.</span>
       <a class="btn btn--ghost" href="#/playlists">Back</a></div>`;
        return;
    }

    document.title = `Melo — ${playlist.name}`;
    const root = document.getElementById('playlist-detail-root');
    if (!root) return;

    const currentSongId = player.getCurrentSongId?.() ?? null;
    const rows = (playlist.songs ?? []).map((s, i) => `
    <div class="playlist-song-row">
      <span class="playlist-song-row__pos">${i + 1}</span>
      ${renderSongCard(s, s.id === currentSongId, [])}
      <button class="icon-btn" data-action="remove-from-playlist"
              data-playlist-id="${id}" data-song-id="${s.id}"
              aria-label="Remove from playlist">✕</button>
    </div>`).join('');

    root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${escHtml(playlist.name)}</h1>
    </div>
    <div class="song-list" role="list">${rows || buildEmptyPlaylist()}</div>`;
}

function buildEmptyPlaylist() {
    return `<div class="empty-state"><span class="empty-state__label">No songs in playlist.</span></div>`;
}

// ── Add Song Modal ────────────────────────────────────────────────────────

function openAddSongModal() {
    const root = document.getElementById('modal-root');
    root.innerHTML = buildStep1Html();
    bindStep1Events();
}

function buildStep1Html(error = '') {
    return `<div class="modal-overlay" id="modal-overlay">
    <div class="modal">
      <h2 class="modal__title">Add Song</h2>
      <div class="modal__field">
        <label class="modal__label" for="url-input">YouTube URL</label>
        <input class="modal__input" id="url-input" type="url"
               placeholder="https://youtube.com/watch?v=…" autocomplete="off" />
        <div class="modal__error">${escHtml(error)}</div>
      </div>
      <div class="modal__footer">
        <button class="btn btn--ghost" data-action="close-modal">Cancel</button>
        <button class="btn btn--accent" id="btn-preview" disabled>Preview</button>
      </div>
    </div>
  </div>`;
}

function buildStep1LoadingHtml(url) {
    return `<div class="modal-overlay" id="modal-overlay">
    <div class="modal">
      <h2 class="modal__title">Add Song</h2>
      <div class="modal__field">
        <label class="modal__label" for="url-input">YouTube URL</label>
        <input class="modal__input" id="url-input" type="url"
               value="${escHtml(url)}" autocomplete="off" disabled />
        <div class="modal__error"></div>
      </div>
      <div class="modal__footer">
        <button class="btn btn--ghost" data-action="close-modal">Cancel</button>
        <button class="btn btn--accent" disabled>
          ${spinnerSvg()} Fetching…
        </button>
      </div>
    </div>
  </div>`;
}

function spinnerSvg() {
    return `<svg class="spinner" width="14" height="14" viewBox="0 0 14 14" fill="none"
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="2" stroke-dasharray="26" stroke-dashoffset="10" stroke-linecap="round"/>
  </svg>`;
}

function bindStep1Events() {
    const overlay = document.getElementById('modal-overlay');
    const urlInput = document.getElementById('url-input');
    const btnPreview = document.getElementById('btn-preview');

    urlInput?.focus();

    urlInput?.addEventListener('input', () => {
        btnPreview.disabled = !urlInput.value.trim();
    });

    btnPreview?.addEventListener('click', () => fetchPreview(urlInput.value.trim()));

    urlInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !btnPreview.disabled) fetchPreview(urlInput.value.trim());
    });

    overlay?.addEventListener('click', e => {
        if (e.target === overlay) closeModal();
    });
}

async function fetchPreview(url) {
    // Show spinner while loading
    const root = document.getElementById('modal-root');
    root.innerHTML = buildStep1LoadingHtml(url);
    document.getElementById('modal-overlay')?.addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') closeModal();
    });

    let meta;
    try {
        meta = await api.previewSong(url);
    } catch (err) {
        root.innerHTML = buildStep1Html(err.message);
        bindStep1Events();
        document.getElementById('url-input').value = url;
        document.getElementById('btn-preview').disabled = false;
        return;
    }

    showStep2(url, meta);
}

function showStep2(url, meta) {
    const root = document.getElementById('modal-root');
    const duration = formatDuration(meta.duration);

    root.innerHTML = `<div class="modal-overlay" id="modal-overlay">
    <div class="modal">
      <h2 class="modal__title">Confirm & Trim</h2>
      <div class="modal__preview">
        <img class="modal__preview-thumb" src="${escHtml(meta.thumbnail_url ?? '')}" alt="" />
        <div class="modal__preview-info">
          <div class="modal__preview-title">${escHtml(meta.title ?? '')}</div>
          <div class="modal__preview-meta">${escHtml(meta.channel ?? '')} · ${duration}</div>
        </div>
      </div>
      <div class="modal__params">
        <div class="modal__field">
          <label class="modal__label" for="start-input">Start (sec)</label>
          <input class="modal__input" id="start-input" type="number" min="0" placeholder="0" />
        </div>
        <div class="modal__field">
          <label class="modal__label" for="end-input">End (sec)</label>
          <input class="modal__input" id="end-input" type="number" min="1" placeholder="${Math.floor(meta.duration ?? 0)}" />
        </div>
        <div class="modal__field modal__params-full">
          <label class="modal__label" for="speed-select">Speed</label>
          <select class="modal__input" id="speed-select">
            <option value="0.5">0.5×</option>
            <option value="0.75">0.75×</option>
            <option value="1.0" selected>1.0×</option>
            <option value="1.25">1.25×</option>
            <option value="1.5">1.5×</option>
            <option value="2.0">2.0×</option>
            <option value="4.0">4.0×</option>
          </select>
        </div>
      </div>
      <div class="modal__footer">
        <button class="btn btn--ghost" data-action="close-modal">Cancel</button>
        <button class="btn btn--accent" id="btn-submit-song">Add to Melo</button>
      </div>
    </div>
  </div>`;

    document.getElementById('modal-overlay')?.addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') closeModal();
    });

    document.getElementById('btn-submit-song')?.addEventListener('click', () =>
        submitSong(url)
    );
}

async function submitSong(url) {
    const start = parseFloat(document.getElementById('start-input')?.value) || undefined;
    const end = parseFloat(document.getElementById('end-input')?.value) || undefined;
    const speed = parseFloat(document.getElementById('speed-select')?.value) || 1.0;

    const params = { url };
    if (start !== undefined) params.start = start;
    if (end !== undefined) params.end = end;
    if (speed !== 1.0) params.speed = speed;

    try {
        await api.submitSong(params);
        closeModal();
        renderToast('Added to Melo — processing…');
        if (window.location.hash === '#/' || window.location.hash === '') {
            stopPoll();
            await loadLibrarySongs(false);
        }
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

function closeModal() {
    document.getElementById('modal-root').innerHTML = '';
}

// ── Favorite Toggle ───────────────────────────────────────────────────────

async function handleFavoriteToggle(songId, currentlyFavorited) {
    const btn = document.querySelector(`[data-action="toggle-favorite"][data-song-id="${songId}"]`);
    if (!btn) return;

    const nextFav = !currentlyFavorited;
    btn.classList.toggle('icon-btn--active', nextFav);

    try {
        if (currentlyFavorited) {
            await api.removeFavorite(songId);
        } else {
            await api.addFavorite(songId);
            renderToast('Added to favorites');
        }
    } catch (err) {
        btn.classList.toggle('icon-btn--active', currentlyFavorited); // revert
        renderToast(err.message, 'error');
    }
}

// ── Delete Song ───────────────────────────────────────────────────────────

function confirmDeleteSong(songId) {
    const root = document.getElementById('modal-root');
    root.innerHTML = `<div class="modal-overlay" id="modal-overlay">
    <div class="modal confirm-dialog">
      <h2 class="modal__title">Delete Song</h2>
      <p class="confirm-dialog__msg">Delete this song? This cannot be undone.</p>
      <div class="modal__footer">
        <button class="btn btn--ghost" data-action="close-modal">Cancel</button>
        <button class="btn btn--danger" id="btn-confirm-delete">Delete</button>
      </div>
    </div>
  </div>`;

    document.getElementById('btn-confirm-delete')?.addEventListener('click', () =>
        doDeleteSong(songId)
    );

    document.getElementById('modal-overlay')?.addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') closeModal();
    });
}

async function doDeleteSong(songId) {
    try {
        await api.deleteSong(songId);
        closeModal();
        renderToast('Song deleted');
        if (player.isSongLoaded(songId)) {
            document.getElementById('player-bar').classList.add('player-bar--empty');
        }
        route();
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

// ── Retry Failed Song ─────────────────────────────────────────────────────

async function handleRetrySong(songId) {
    let song;
    try {
        song = await api.getSong(songId);
    } catch (err) {
        renderToast(err.message, 'error');
        return;
    }

    const url = `https://www.youtube.com/watch?v=${song.youtube_id}`;
    const params = { url };
    if (song.start != null) params.start = song.start;
    if (song.end != null) params.end = song.end;
    if (song.speed && song.speed !== 1.0) params.speed = song.speed;

    try {
        await api.deleteSong(songId);
        await api.submitSong(params);
        renderToast('Retrying…');
        if (window.location.hash === '#/' || window.location.hash === '') {
            stopPoll();
            await loadLibrarySongs(false);
        }
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

// ── Add to Playlist ───────────────────────────────────────────────────────

async function handleAddToPlaylist(playlistName, songId) {
    const playlist = state.playlists.find(p => p.name === playlistName);
    if (!playlist) return;
    try {
        await api.addSongToPlaylist(playlist.id, songId);
        renderToast(`Added to "${playlistName}"`);
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

async function handleNewPlaylistForSong(songId) {
    const name = window.prompt('New playlist name:')?.trim();
    if (!name) return;
    try {
        const playlist = await api.createPlaylist(name);
        await api.addSongToPlaylist(playlist.id, songId);
        state.playlists.push(playlist);
        renderToast(`Added to "${name}"`);
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

// ── Global Event Delegation ───────────────────────────────────────────────

function bindGlobalEvents() {
    document.addEventListener('click', handleGlobalClick);
    document.addEventListener('keydown', handleKeydown);
    document.getElementById('btn-add-song')?.addEventListener('click', openAddSongModal);
}

function handleGlobalClick(e) {
    // Close open dropdowns on outside click
    const clickedDropdown = e.target.closest('[data-dropdown]');
    document.querySelectorAll('.dropdown__menu').forEach(menu => {
        const dropdown = menu.closest('[data-dropdown]');
        if (dropdown !== clickedDropdown) menu.style.display = 'none';
    });

    // Song card click → play (BEFORE action guard)
    const card = e.target.closest('.song-card[data-playable="true"]');
    if (card && !e.target.closest('[data-action]')) {
        playSongById(card.dataset.songId);
        return;
    }

    // Playlist card click → navigate (BEFORE action guard)
    const playlistCard = e.target.closest('.playlist-card');
    if (playlistCard && !e.target.closest('[data-action]')) {
        window.location.hash = `#/playlists/${playlistCard.dataset.playlistId}`;
        return;
    }

    const action = e.target.closest('[data-action]')?.dataset.action;
    if (!action) return;

    const el = e.target.closest('[data-action]');
    const songId = el?.dataset.songId;

    switch (action) {
        case 'open-add-song':
            openAddSongModal();
            break;
        case 'close-modal':
            closeModal();
            break;
        case 'toggle-favorite': {
            const isFav = el.classList.contains('icon-btn--active');
            handleFavoriteToggle(songId, isFav);
            break;
        }
        case 'open-menu': {
            const menu = el.closest('[data-dropdown]').querySelector('.dropdown__menu');
            menu.style.display = menu.style.display === 'none' ? '' : 'none';
            e.stopPropagation();
            break;
        }
        case 'delete-song':
            confirmDeleteSong(songId);
            break;
        case 'retry-song':
            handleRetrySong(songId);
            break;
        case 'add-to-playlist':
            handleAddToPlaylist(el.dataset.playlistName, songId);
            break;
        case 'new-playlist-for-song':
            handleNewPlaylistForSong(songId);
            break;
        case 'remove-from-playlist': {
            const playlistId = el.dataset.playlistId;
            handleRemoveFromPlaylist(playlistId, songId);
            break;
        }
    }
}

function handleKeydown(e) {
    if (e.key === 'Escape') closeModal();
    if (e.key === ' ' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
        e.preventDefault();
        player.togglePlayPause();
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────

async function playSongById(id) {
    try {
        const song = await api.getSong(id);
        player.loadSong(song);
        // Full DOM re-render of all visible song cards to sync active state
        document.querySelectorAll('.song-card').forEach(card => {
            const isActive = card.dataset.songId === id;
            card.classList.toggle('song-card--active', isActive);
            const titleEl = card.querySelector('.song-card__title');
            if (titleEl) titleEl.style.color = isActive ? 'var(--accent)' : '';
        });
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

async function handleRemoveFromPlaylist(playlistId, songId) {
    try {
        await api.removeSongFromPlaylist(playlistId, songId);
        renderToast('Removed from playlist');
        await refreshPlaylistDetail(playlistId);
    } catch (err) {
        renderToast(err.message, 'error');
    }
}

async function checkApiHealth() {
    try {
        const health = await api.checkHealth();
        if (health.status !== 'ok') showHealthBanner('Some services degraded. Check server logs.');
    } catch {
        showHealthBanner('Cannot reach API. Is the server running?');
    }
}

function showHealthBanner(msg) {
    const el = document.createElement('div');
    el.className = 'health-banner';
    el.textContent = msg;
    document.body.prepend(el);
}

function formatDuration(seconds) {
    if (!seconds) return '';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function escHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Preload playlist cache for overflow menus
(async () => {
    try {
        const data = await api.listPlaylists();
        state.playlists = data.records;
    } catch { /* non-fatal */ }
})();
