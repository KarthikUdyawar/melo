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
    playlists: [], // cache for overflow menu
    routeToken: 0,
    loadedCount: 0, // Number of songs currently rendered in the library view.
    currentSongList: [], // Song objects backing the currently rendered list —
    // becomes the player queue when a card is clicked.
    currentPlaylistId: null, // needed by drop handler (delegation has no closure)
    dragSongId: null, // dragged song id, tracked outside dataTransfer
    nowPlayingUnsub: null, // unsubscribe fn for the Now Playing panel's player.subscribe()
    nowPlayingSongId: null, // last songId drawn on the waveform, avoids redundant redraw
    npSeeking: false, // true while dragging the panel scrubber — mirrors player.js's isSeeking
    npDuration: 0, // last known duration, used for live time label while dragging
};

// ── Boot ──────────────────────────────────────────────────────────────────

async function bootstrap() {
    player.bindPlayerControls();
    bindGlobalEvents();
    checkApiHealth();

    // Preload playlists before first render so song-card menus
    // have playlist options available immediately.
    try {
        const data = await api.listPlaylists();
        state.playlists = data.records;
    } catch {
        // non-fatal
    }

    route();
}

bootstrap();

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
    // Matches sidebar links AND the phone tab-bar links (both carry .nav-link).
    document.querySelectorAll('.nav-link').forEach(link => {
        const route = link.dataset.route;
        const active =
            (route === '/' && (hash === '#/' || hash === '#')) ||
            (route !== '/' && hash.startsWith(`#${route}`));
        link.classList.toggle('nav-link--active', active);
    });
}

function nextRouteToken() {
    state.routeToken += 1;
    return state.routeToken;
}

// ── Library Page ──────────────────────────────────────────────────────────

async function renderLibraryPage() {
    const token = nextRouteToken();

    document.title = 'Melo — Library';
    state.bookmark = null;
    state.loadedCount = 0;

    const content = document.getElementById('page-content');
    content.innerHTML = buildLibraryShell();

    bindLibraryFilterEvents();

    await loadLibrarySongs(false, token);
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

async function loadLibrarySongs(append, token = state.routeToken) {
    const params = { ...state.libraryQuery };

    if (state.bookmark) {
        params.after = state.bookmark;
    }

    let data;

    try {
        data = await api.listSongs(params);
    } catch (err) {
        if (token !== state.routeToken) return;
        renderToast(err.message, 'error');
        return;
    }

    if (token !== state.routeToken) return;

    const list = document.getElementById('song-list');
    if (!list) return;

    const currentSongId = player.getCurrentSongId?.() ?? null;

    const cards = data.records
        .map(song =>
            renderSongCard(
                song,
                song.id === currentSongId,
                state.playlists.map(p => p.name)
            )
        )
        .join('');

    if (append) {
        list.insertAdjacentHTML('beforeend', cards);
        state.loadedCount += data.records.length;
        state.currentSongList = state.currentSongList.concat(data.records);
    } else {
        list.innerHTML =
            data.records.length === 0
                ? buildEmptyLibrary()
                : cards;

        state.loadedCount = data.records.length;
        state.currentSongList = data.records;
    }

    // Only show "Load more" if the API returned a full page AND there's a bookmark.
    // A partial page means we've reached the end even if bookmark is non-null.
    const limit = parseInt(state.libraryQuery.limit, 10) || 50;
    const hasMore = !!data.bookmark && data.records.length >= limit;

    state.bookmark = hasMore ? data.bookmark : null;

    const loadMoreWrap = document.getElementById('load-more-wrap');

    if (loadMoreWrap) {
        loadMoreWrap.style.display = hasMore ? '' : 'none';
    }

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
    const params = {
        ...state.libraryQuery,
        limit: String(
            Math.max(
                state.loadedCount,
                parseInt(state.libraryQuery.limit, 10) || 50
            )
        ),
    };

    let data;

    try {
        data = await api.listSongs(params);
    } catch {
        return;
    }

    const list = document.getElementById('song-list');

    if (!list) {
        stopPoll();
        return;
    }

    const currentSongId = player.getCurrentSongId?.() ?? null;

    list.innerHTML = data.records
        .map(song =>
            renderSongCard(
                song,
                song.id === currentSongId,
                state.playlists.map(p => p.name)
            )
        )
        .join('');

    state.loadedCount = data.records.length;
    state.currentSongList = data.records;

    const stillPending = data.records.some(
        song =>
            song.status === 'pending' ||
            song.status === 'processing'
    );

    if (!stillPending) {
        stopPoll();
    }
}

function stopPoll() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}

// ── Favorites Page ────────────────────────────────────────────────────────

async function renderFavoritesPage() {
    const token = nextRouteToken();

    document.title = 'Melo — Favorites';

    const content = document.getElementById('page-content');

    content.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Favorites</h1>
      </div>
      <div class="song-list" id="song-list" role="list"></div>
    `;

    let data;

    try {
        data = await api.listFavorites();
    } catch (err) {
        if (token !== state.routeToken) return;
        renderToast(err.message, 'error');
        return;
    }

    if (token !== state.routeToken) return;

    const list = document.getElementById('song-list');
    if (!list) return;

    state.currentSongList = data.records;
    const currentSongId = player.getCurrentSongId?.() ?? null;

    list.innerHTML =
        data.records.length === 0
            ? `<div class="empty-state">
                 <span class="empty-state__label">No favorites yet.</span>
               </div>`
            : data.records
                .map(song =>
                    renderSongCard(
                        song,
                        song.id === currentSongId,
                        state.playlists.map(p => p.name)
                    )
                )
                .join('');
}

// ── Playlists Page ────────────────────────────────────────────────────────

async function renderPlaylistsPage() {
    const token = nextRouteToken();

    document.title = 'Melo — Playlists';

    const content = document.getElementById('page-content');

    content.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Playlists</h1>
        <button class="btn btn--ghost" id="btn-new-playlist">
          + New Playlist
        </button>
      </div>
      <div id="new-playlist-wrap"></div>
      <div class="playlist-grid" id="playlist-grid" role="list"></div>
    `;

    document
        .getElementById('btn-new-playlist')
        ?.addEventListener('click', showNewPlaylistInput);

    await refreshPlaylistGrid(token);
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

async function refreshPlaylistGrid(token = state.routeToken) {
    let data;
    try { data = await api.listPlaylists(); } catch (err) {
        renderToast(err.message, 'error'); return;
    }
    if (token !== state.routeToken) return;
    state.playlists = data.records;
    const grid = document.getElementById('playlist-grid');
    if (!grid) return;
    grid.innerHTML = data.records.length === 0
        ? `<div class="empty-state"><span class="empty-state__label">No playlists yet.</span></div>`
        : data.records.map(renderPlaylistCard).join('');
}

// ── Playlist Detail Page ──────────────────────────────────────────────────

async function renderPlaylistDetailPage(id) {
    const token = nextRouteToken();
    document.title = 'Melo — Playlist';
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <a class="back-link" href="#/playlists">
        ← Playlists
      </a>
      <div id="playlist-detail-root"></div>
    `;
    await refreshPlaylistDetail(id, token);
}

async function refreshPlaylistDetail(id, token = state.routeToken) {
    let playlist;
    if (token !== state.routeToken) return;
    try { playlist = await api.getPlaylist(id); } catch {
        if (token !== state.routeToken) return;
        document.getElementById('playlist-detail-root').innerHTML =
            `<div class="empty-state"><span class="empty-state__label">Playlist not found.</span>
       <a class="btn btn--ghost" href="#/playlists">Back</a></div>`;
        return;
    }
    if (token !== state.routeToken) return;
    document.title = `Melo — ${playlist.name}`;
    const root = document.getElementById('playlist-detail-root');
    if (!root) return;
    state.currentPlaylistId = id;
    state.currentSongList = playlist.songs ?? [];
    root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">${escHtml(playlist.name)}</h1>
    </div>
    <div class="song-list" id="playlist-song-list" role="list"></div>`;
    renderPlaylistRows(id, state.currentSongList);
}

function renderPlaylistRows(playlistId, songs) {
    const list = document.getElementById('playlist-song-list');
    if (!list) return;
    const currentSongId = player.getCurrentSongId?.() ?? null;
    list.innerHTML = songs.length
        ? songs
            .map((s, i) => buildPlaylistRow(s, i, playlistId, s.id === currentSongId))
            .join('')
        : buildEmptyPlaylist();
}

function buildPlaylistRow(song, position, playlistId, isActive) {
    const total = state.currentSongList.length;
    return `
    <div class="playlist-song-row"
         draggable="true"
         tabindex="0"
         aria-label="${escHtml(song.title ?? 'Song')}, position ${position + 1} of ${total}"
         data-position="${position}"
         data-song-id="${song.id}">
      <span class="playlist-song-row__pos">${position + 1}</span>
      ${renderSongCard(song, isActive, [])}
      <span class="sr-only">Press Arrow Up or Arrow Down to reorder.</span>
      <button class="icon-btn" data-action="remove-from-playlist"
              data-playlist-id="${playlistId}" data-song-id="${song.id}"
              aria-label="Remove from playlist">✕</button>
    </div>`;
}

function buildEmptyPlaylist() {
    return `<div class="empty-state"><span class="empty-state__label">No songs in playlist.</span></div>`;
}

// ── Playlist Drag Reorder ─────────────────────────────────────────────────

function handleDragStart(e) {
    const row = e.target.closest('.playlist-song-row[draggable="true"]');
    if (!row) return;
    state.dragSongId = row.dataset.songId;
    e.dataTransfer.effectAllowed = 'move';
    row.classList.add('playlist-song-row--dragging');
}

function handleDragOver(e) {
    const row = e.target.closest('.playlist-song-row');
    if (!row || !state.dragSongId) return;
    e.preventDefault(); // required to allow drop
    row.classList.add('playlist-song-row--drag-over');
}

function handleDragLeave(e) {
    e.target.closest('.playlist-song-row')?.classList.remove('playlist-song-row--drag-over');
}

function handleDrop(e) {
    const row = e.target.closest('.playlist-song-row');
    if (!row || !state.dragSongId) return;
    e.preventDefault();
    row.classList.remove('playlist-song-row--drag-over');
    const targetSongId = row.dataset.songId;
    const targetPosition = parseInt(row.dataset.position, 10);
    if (targetSongId !== state.dragSongId) {
        reorderPlaylistSongOptimistic(state.currentPlaylistId, state.dragSongId, targetPosition);
    }
    state.dragSongId = null;
}

function handleDragEnd() {
    document.querySelectorAll('.playlist-song-row--dragging, .playlist-song-row--drag-over')
        .forEach(el => el.classList.remove('playlist-song-row--dragging', 'playlist-song-row--drag-over'));
    state.dragSongId = null;
}

async function reorderPlaylistSongOptimistic(playlistId, songId, newPosition) {
    const songs = state.currentSongList;
    const oldIndex = songs.findIndex(s => s.id === songId);
    if (oldIndex === -1 || oldIndex === newPosition) return;
    // Optimistic local reorder — insert-after-target semantics, matches
    // "drop onto row N" as "place after row N" rather than "before".
    const reordered = songs.slice();
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newPosition, 0, moved);
    state.currentSongList = reordered;
    renderPlaylistRows(playlistId, reordered);
    try {
        await api.reorderSongInPlaylist(playlistId, songId, newPosition);
    } catch (err) {
        renderToast(err.message, 'error');
        await refreshPlaylistDetail(playlistId); // resync from server on failure
    }
}

// ── Now Playing Panel (FE-3) ──────────────────────────────────────────────

function openNowPlayingPanel() {
    const song = player.getCurrentSong();
    if (!song) return;

    const root = document.getElementById('now-playing-root');
    root.innerHTML = buildNowPlayingHtml(song);
    bindNowPlayingEvents();

    state.nowPlayingSongId = null; // force waveform draw on first subscribe tick
    state.nowPlayingUnsub = player.subscribe(updateNowPlayingUi);

    loadAndDrawWaveform(song.id);
}

function closeNowPlayingPanel() {
    state.nowPlayingUnsub?.();
    state.nowPlayingUnsub = null;
    document.getElementById('now-playing-root').innerHTML = '';
}

function isNowPlayingOpen() {
    return !!document.getElementById('now-playing-root')?.firstElementChild;
}

function buildNowPlayingHtml(song) {
    return `<div class="now-playing-overlay" id="now-playing-overlay">
    <div class="now-playing">
      <button class="icon-btn now-playing__close" id="np-close" aria-label="Close">✕</button>
      <img class="now-playing__thumb" id="np-thumb" src="${escHtml(song.thumbnail_url ?? '')}" alt="" />
      <div class="now-playing__title" id="np-title">${escHtml(song.title ?? '')}</div>
      <div class="now-playing__channel" id="np-channel">${escHtml(song.channel ?? '')}</div>
      <canvas class="now-playing__canvas" id="np-canvas"></canvas>
      <div class="now-playing__transport">
        <button class="player-btn" id="np-shuffle" aria-label="Shuffle" aria-pressed="false">${shuffleSvg()}</button>
        <button class="player-btn" id="np-prev" aria-label="Previous">${prevSvg()}</button>
        <button class="player-btn" id="np-play-pause" aria-label="Play / Pause">
          <svg id="np-icon-play" width="24" height="24" viewBox="0 0 20 20" fill="currentColor"><path d="M6 4l10 6-10 6V4z"/></svg>
          <svg id="np-icon-pause" width="24" height="24" viewBox="0 0 20 20" fill="currentColor" style="display:none"><rect x="4" y="3" width="4" height="14" rx="1"/><rect x="12" y="3" width="4" height="14" rx="1"/></svg>
        </button>
        <button class="player-btn" id="np-next" aria-label="Next">${nextSvg()}</button>
        <button class="player-btn loop-btn" id="np-loop" aria-label="Enable loop" data-mode="off">${loopSvg()}<span class="loop-badge" aria-hidden="true">1</span></button>
      </div>
      <input type="range" class="player-scrubber" id="np-scrubber" min="0" max="100" value="0" step="0.1" aria-label="Seek" disabled />
      <span class="player-time" id="np-time">0:00 / 0:00</span>
      <div class="player-volume" id="np-volume">
        <button class="player-btn" id="np-mute" aria-label="Mute">${volumeSvg()}</button>
        <input type="range" class="volume-slider" id="np-volume-slider" min="0" max="1" value="1" step="0.01" aria-label="Volume" />
      </div>
    </div>
  </div>`;
}

function bindNowPlayingEvents() {
    document.getElementById('np-close')?.addEventListener('click', closeNowPlayingPanel);
    document.getElementById('now-playing-overlay')?.addEventListener('click', e => {
        if (e.target.id === 'now-playing-overlay') closeNowPlayingPanel();
    });
    document.getElementById('np-play-pause')?.addEventListener('click', player.togglePlayPause);
    document.getElementById('np-prev')?.addEventListener('click', player.prev);
    document.getElementById('np-next')?.addEventListener('click', player.next);
    document.getElementById('np-shuffle')?.addEventListener('click', player.toggleShuffle);
    document.getElementById('np-loop')?.addEventListener('click', player.cycleLoopMode);
    document.getElementById('np-mute')?.addEventListener('click', player.toggleMute);
    document.getElementById('np-volume-slider')?.addEventListener('input', e =>
        player.setVolume(parseFloat(e.target.value))
    );
    bindNowPlayingScrubber();
}

function bindNowPlayingScrubber() {
    const scrubber = document.getElementById('np-scrubber');
    if (!scrubber) return;
    scrubber.removeAttribute('disabled');

    scrubber.addEventListener('mousedown', () => { state.npSeeking = true; });
    scrubber.addEventListener('touchstart', () => { state.npSeeking = true; });

    scrubber.addEventListener('input', () => {
        if (!state.npDuration) return;
        const seekTime = (scrubber.value / 100) * state.npDuration;
        const time = document.getElementById('np-time');
        if (time) time.textContent = `${formatDuration(seekTime)} / ${formatDuration(state.npDuration)}`;
    });

    scrubber.addEventListener('change', () => {
        player.seekTo(parseFloat(scrubber.value));
        state.npSeeking = false;
    });

    scrubber.addEventListener('mouseup', () => { state.npSeeking = false; });
    scrubber.addEventListener('touchend', () => { state.npSeeking = false; });
}

/** Mirrors player.js state onto the panel's own DOM. Does NOT touch the
 *  player-bar elements — player.js already owns those via its own listeners. */
function updateNowPlayingUi(s) {
    if (!isNowPlayingOpen()) return;

    if (s.song && s.song.id !== state.nowPlayingSongId) {
        document.getElementById('np-thumb').src = s.song.thumbnail_url ?? '';
        document.getElementById('np-title').textContent = s.song.title ?? '';
        document.getElementById('np-channel').textContent = s.song.channel ?? '';
        loadAndDrawWaveform(s.song.id);
    }

    const playIcon = document.getElementById('np-icon-play');
    const pauseIcon = document.getElementById('np-icon-pause');
    if (playIcon) playIcon.style.display = s.paused ? '' : 'none';
    if (pauseIcon) pauseIcon.style.display = s.paused ? 'none' : '';

    state.npDuration = s.duration || 0;

    const scrubber = document.getElementById('np-scrubber');
    if (scrubber && s.duration && !state.npSeeking) scrubber.value = (s.currentTime / s.duration) * 100;

    const time = document.getElementById('np-time');
    if (time && !state.npSeeking) time.textContent = `${formatDuration(s.currentTime)} / ${formatDuration(s.duration)}`;

    const volSlider = document.getElementById('np-volume-slider');
    if (volSlider) volSlider.value = s.volume;

    document.getElementById('np-shuffle')?.setAttribute('aria-pressed', String(s.shuffle));
    const loopBtn = document.getElementById('np-loop');
    if (loopBtn) loopBtn.dataset.mode = s.loopMode;
}

async function loadAndDrawWaveform(songId) {
    state.nowPlayingSongId = songId;
    const canvas = document.getElementById('np-canvas');
    if (!canvas) return;

    let peaks;
    try {
        peaks = await player.getPeaks(songId);
    } catch {
        return; // waveform is visual-only; silent fail, no toast noise
    }

    if (!isNowPlayingOpen() || state.nowPlayingSongId !== songId) return;

    drawWaveform(canvas, peaks);
}

function drawWaveform(canvas, peaks) {
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    ctx.fillStyle = accent || '#c8f04e';

    const barGap = 2;
    const barWidth = width / peaks.length - barGap;
    const mid = height / 2;

    peaks.forEach((peak, i) => {
        const barHeight = Math.max(2, peak * height);
        const x = i * (barWidth + barGap);
        ctx.fillRect(x, mid - barHeight / 2, barWidth, barHeight);
    });
}

function shuffleSvg() {
    return `<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 5h3.5L13 15h5"/><path d="M14.5 5H18v3.5"/><path d="M2 15h3.5L9 10"/><path d="M14.5 15H18v-3.5"/></svg>`;
}
function prevSvg() {
    return `<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path d="M6 4h2v12H6zM16 4v12L7 10z"/></svg>`;
}
function nextSvg() {
    return `<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path d="M14 4h-2v12h2zM4 4v12l9-6z"/></svg>`;
}
function loopSvg() {
    return `<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3l3 3-3 3"/><path d="M3 11V9a3 3 0 0 1 3-3h11"/><path d="M6 17l-3-3 3-3"/><path d="M17 9v2a3 3 0 0 1-3 3H3"/></svg>`;
}
function volumeSvg() {
    return `<svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path d="M3 8v4h3l4 4V4L6 8H3z"/></svg>`;
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

    const overlay = document.getElementById('modal-overlay');

    overlay?.addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') closeModal();
    });

    let meta;

    try {
        meta = await api.previewSong(url);
    } catch (err) {
        // Ignore stale responses if the modal was closed/replaced
        if (!overlay?.isConnected) {
            return;
        }

        root.innerHTML = buildStep1Html(err.message);
        bindStep1Events();

        const urlInput = document.getElementById('url-input');
        const btnPreview = document.getElementById('btn-preview');

        if (urlInput) {
            urlInput.value = url;
        }

        if (btnPreview) {
            btnPreview.disabled = false;
        }

        return;
    }

    // Ignore stale responses if the modal was closed/replaced
    if (!overlay?.isConnected) {
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
        // Submit replacement first.
        await api.submitSong(params);

        // Only remove the failed entry after a successful submit.
        await api.deleteSong(songId);

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
    document.addEventListener('dragstart', handleDragStart);
    document.addEventListener('dragover', handleDragOver);
    document.addEventListener('dragleave', handleDragLeave);
    document.addEventListener('drop', handleDrop);
    document.addEventListener('dragend', handleDragEnd);
    document
        .querySelectorAll('.btn-add-song-trigger')
        .forEach(btn => btn.addEventListener('click', openAddSongModal));
    document.getElementById('player-info-trigger')?.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openNowPlayingPanel(); }
    });
}

function handleGlobalClick(e) {
    // Close open dropdowns on outside click
    const clickedDropdown = e.target.closest('[data-dropdown]');
    document.querySelectorAll('.dropdown__menu').forEach(menu => {
        const dropdown = menu.closest('[data-dropdown]');
        if (dropdown !== clickedDropdown) {
            menu.style.display = 'none';
            dropdown?.querySelector('[data-action="open-menu"]')?.setAttribute('aria-expanded', 'false');
        }
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
        case 'open-now-playing':
            openNowPlayingPanel();
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
            const opening = menu.style.display === 'none';
            menu.style.display = opening ? '' : 'none';
            el.setAttribute('aria-expanded', String(opening));
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
        case 'delete-playlist': {
            const playlistId = el.dataset.playlistId;
            confirmDeletePlaylist(playlistId);
            break;
        }
    }
}

function handleKeydown(e) {
    if (e.key === 'Escape') {
        if (isNowPlayingOpen()) { closeNowPlayingPanel(); return; }
        if (closeOpenDropdown()) return;
        closeModal();
        return;
    }
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        handlePlaylistRowKeydown(e);
        return;
    }
    if (e.key === 'Tab') {
        const container = document.querySelector('.now-playing') || document.querySelector('.modal');
        if (container) trapFocus(container, e);
    }
    if (e.key === ' ' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT') {
        e.preventDefault();
        player.togglePlayPause();
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────

function playSongById(id) {
    // state.currentSongList always mirrors the page currently on screen —
    // becomes the player's queue so prev/next/shuffle/loop have context.
    player.setQueueAndPlay(state.currentSongList, id);

    // Full DOM re-render of all visible song cards to sync active state
    document.querySelectorAll('.song-card').forEach(card => {
        const isActive = card.dataset.songId === id;
        card.classList.toggle('song-card--active', isActive);
        const titleEl = card.querySelector('.song-card__title');
        if (titleEl) titleEl.style.color = isActive ? 'var(--accent)' : '';
    });
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

function confirmDeletePlaylist(playlistId) {
    const root = document.getElementById('modal-root');
    root.innerHTML = `<div class="modal-overlay" id="modal-overlay">
    <div class="modal confirm-dialog">
      <h2 class="modal__title">Delete Playlist</h2>
      <p class="confirm-dialog__msg">Delete this playlist? This cannot be undone.</p>
      <div class="modal__footer">
        <button class="btn btn--ghost" data-action="close-modal">Cancel</button>
        <button class="btn btn--danger" id="btn-confirm-delete-playlist">Delete</button>
      </div>
    </div>
  </div>`;

    document.getElementById('btn-confirm-delete-playlist')?.addEventListener('click', () =>
        doDeletePlaylist(playlistId)
    );

    document.getElementById('modal-overlay')?.addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') closeModal();
    });
}

async function doDeletePlaylist(playlistId) {
    try {
        await api.deletePlaylist(playlistId);
        closeModal();
        renderToast('Playlist deleted');
        await refreshPlaylistGrid();
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

// ── Accessibility: focus trap + dropdown close ──────────────────────────

function closeOpenDropdown() {
    const openMenu = [...document.querySelectorAll('.dropdown__menu')]
        .find(m => m.style.display !== 'none');
    if (!openMenu) return false;
    openMenu.style.display = 'none';
    openMenu.closest('[data-dropdown]')?.querySelector('[data-action="open-menu"]')
        ?.setAttribute('aria-expanded', 'false');
    return true;
}

function trapFocus(container, e) {
    if (e.key !== 'Tab') return;
    const focusables = [...container.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )].filter(el => !el.disabled && el.offsetParent !== null);
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
    }
}

function handlePlaylistRowKeydown(e) {
    const row = e.target.closest('.playlist-song-row');
    if (!row || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;

    e.preventDefault();

    const songId = row.dataset.songId;
    const currentPos = parseInt(row.dataset.position, 10);
    const newPos = currentPos + (e.key === 'ArrowUp' ? -1 : 1);

    if (newPos < 0 || newPos > state.currentSongList.length - 1) return;

    reorderPlaylistSongOptimistic(state.currentPlaylistId, songId, newPos).then(() => {
        // Row is replaced on re-render — refocus it so keyboard users don't lose their place.
        requestAnimationFrame(() => {
            document
                .querySelector(`.playlist-song-row[data-song-id="${songId}"]`)
                ?.focus();
        });
    });
}
