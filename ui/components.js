/**
 * components.js — pure HTML-string render functions.
 * No side effects. No API calls. No state mutation.
 */

// ── Status Pill ──────────────────────────────────────────────────────────

/** @param {'pending'|'processing'|'done'|'failed'} status */
export function renderStatusPill(status) {
  if (status === 'done') return '';
  const pulse = status === 'processing' ? ' status-dot--pulse' : '';
  return `<span class="status-pill status-pill--${status}">
    <span class="status-dot${pulse}"></span>${status}
  </span>`;
}

// ── Song Card ────────────────────────────────────────────────────────────

/**
 * @param {object} song
 * @param {boolean} isActive
 * @param {string[]} playlistNames  — for overflow menu
 */
export function renderSongCard(song, isActive, playlistNames = []) {
  const activeClass = isActive ? ' song-card--active' : '';
  const heartClass = song.is_favorite ? ' icon-btn--active' : '';
  const heartLabel = song.is_favorite ? 'Remove from favorites' : 'Add to favorites';

  // Escape thumbnail URL before interpolating into src=""
  const thumb = escHtml(song.thumbnail_url ?? '');

  const duration = formatDuration(song.effective_duration ?? song.duration);
  const isPlayable = song.status === 'done';
  const playlistItems = renderPlaylistMenuItems(playlistNames, song.id);

  return `
  <div class="song-card${activeClass}"
       data-song-id="${song.id}"
       data-playable="${isPlayable}"
       role="listitem">
    <img class="song-card__thumb"
         src="${thumb}"
         alt="${escHtml(song.title ?? '')}"
         loading="lazy"
         onerror="this.style.visibility='hidden'" />
    <div class="song-card__body">
      <div class="song-card__title">${escHtml(song.title ?? 'Processing…')}</div>
      <div class="song-card__meta">
        <span>${escHtml(song.channel ?? '')}</span>
        ${song.upload_date ? `<span>·</span><span>${song.upload_date}</span>` : ''}
        ${renderStatusPill(song.status)}
        ${song.status === 'failed' ? renderRetryButton(song.id) : ''}
      </div>
    </div>
    <div class="song-card__actions">
      <span class="song-card__duration">${duration}</span>
      <button class="icon-btn${heartClass}"
              data-action="toggle-favorite"
              data-song-id="${song.id}"
              aria-label="${heartLabel}">
        ${heartSvg(song.is_favorite)}
      </button>
      <div class="dropdown" data-dropdown="${song.id}">
        <button class="icon-btn"
                data-action="open-menu"
                data-song-id="${song.id}"
                aria-label="More options">
          ${moreIcon()}
        </button>
        <div class="dropdown__menu" style="display:none">
          ${playlistItems}
          <div class="dropdown__divider"></div>
          <button class="dropdown__item dropdown__item--danger"
                  data-action="delete-song"
                  data-song-id="${song.id}">Delete</button>
        </div>
      </div>
    </div>
  </div>`;
}

function renderRetryButton(songId) {
  return `<button class="btn btn--retry"
              data-action="retry-song"
              data-song-id="${songId}"
              aria-label="Retry processing">↺ Retry</button>`;
}

function renderPlaylistMenuItems(names, songId) {
  const items = names.map(n =>
    `<button class="dropdown__item"
             data-action="add-to-playlist"
             data-playlist-name="${escHtml(n)}"
             data-song-id="${songId}">${escHtml(n)}</button>`
  ).join('');
  return `${items}
    <button class="dropdown__item"
            data-action="new-playlist-for-song"
            data-song-id="${songId}">+ New playlist</button>`;
}

// ── Playlist Card ─────────────────────────────────────────────────────────

/** @param {{ id: string, name: string, song_count: number, created_at: string }} playlist */
export function renderPlaylistCard(playlist) {
  return `
  <div class="playlist-card" data-playlist-id="${playlist.id}" role="listitem">
    <div class="playlist-card__name">${escHtml(playlist.name)}</div>
    <div class="playlist-card__meta">${playlist.song_count} song${playlist.song_count !== 1 ? 's' : ''}</div>
    <button class="icon-btn icon-btn--danger"
            data-action="delete-playlist"
            data-playlist-id="${playlist.id}"
            aria-label="Delete playlist">✕</button>
  </div>`;
}

// ── Toast ─────────────────────────────────────────────────────────────────

/**
 * Append a self-dismissing toast.
 * @param {string} message
 * @param {'success'|'error'} type
 */
export function renderToast(message, type = 'success') {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const el = document.createElement('div');
  el.className = `toast${type === 'error' ? ' toast--error' : ''}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Helpers ───────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDuration(seconds) {
  if (!seconds) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function heartSvg(filled) {
  return filled
    ? `<svg width="16" height="16" viewBox="0 0 20 20" fill="var(--danger)">
         <path d="M10 17s-7-4.35-7-9a4 4 0 0 1 7-2.65A4 4 0 0 1 17 8c0 4.65-7 9-7 9z"/>
       </svg>`
    : `<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
         <path d="M10 17s-7-4.35-7-9a4 4 0 0 1 7-2.65A4 4 0 0 1 17 8c0 4.65-7 9-7 9z"/>
       </svg>`;
}

function moreIcon() {
  return `<svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
    <circle cx="10" cy="4" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="10" cy="16" r="1.5"/>
  </svg>`;
}
