/**
 * player.js — Single <audio> element. Persists across hash navigation.
 * Owns queue/shuffle/loop/volume state (FE-1).
 */

const audio = document.createElement('audio');
audio.preload = 'none';
document.body.appendChild(audio);

// ── State ─────────────────────────────────────────────────────────────────

let currentSong = null;
let isSeeking = false;

/** @type {object[]} ordered list of song objects the player is traversing */
let queue = [];
let queueIndex = -1;

let shuffle = false; // session-only, tied to current queue
let loopMode = readLoopMode(); // 'off' | 'one' | 'all', persisted
let preMuteVolume = 1.0;

audio.volume = readVolume();

// ── localStorage ─────────────────────────────────────────────────────────

function readVolume() {
    const raw = parseFloat(localStorage.getItem('melo:volume'));
    return Number.isFinite(raw) ? clamp(raw, 0, 1) : 1.0;
}

function readLoopMode() {
    const raw = localStorage.getItem('melo:loop');
    return raw === 'one' || raw === 'all' ? raw : 'off';
}

function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
}

// ── DOM refs ─────────────────────────────────────────────────────────────

const elBar = () => document.getElementById('player-bar');
const elThumb = () => document.getElementById('player-thumb');
const elTitle = () => document.getElementById('player-title');
const elChannel = () => document.getElementById('player-channel');
const elScrubber = () => document.getElementById('player-scrubber');
const elTime = () => document.getElementById('player-time');
const elPlay = () => document.getElementById('icon-play');
const elPause = () => document.getElementById('icon-pause');
const elPrev = () => document.getElementById('btn-prev');
const elNext = () => document.getElementById('btn-next');
const elShuffle = () => document.getElementById('btn-shuffle');
const elLoop = () => document.getElementById('btn-loop');
const elVolumeBtn = () => document.getElementById('btn-mute');
const elVolumeSlider = () => document.getElementById('volume-slider');
const elIconVol = () => document.getElementById('icon-volume');
const elIconMute = () => document.getElementById('icon-muted');

// ── Formatting ───────────────────────────────────────────────────────────

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

// ── UI sync ──────────────────────────────────────────────────────────────

function updatePlayIcon() {
    elPlay().style.display = audio.paused ? '' : 'none';
    elPause().style.display = audio.paused ? 'none' : '';
    emit();
}

function updateScrubber() {
    if (isSeeking) return;
    const scrubber = elScrubber();
    if (!scrubber || !audio.duration || isNaN(audio.duration)) return;
    scrubber.value = (audio.currentTime / audio.duration) * 100;
    elTime().textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    emit();
}

function updateVolumeUi() {
    const slider = elVolumeSlider();
    if (slider) slider.value = audio.volume;

    const muted = audio.volume === 0;
    if (elIconVol()) elIconVol().style.display = muted ? 'none' : '';
    if (elIconMute()) elIconMute().style.display = muted ? '' : 'none';
    elVolumeBtn()?.setAttribute('aria-label', muted ? 'Unmute' : 'Mute');
    emit();
}

function updateShuffleUi() {
    elShuffle()?.setAttribute('aria-pressed', String(shuffle));
    emit();
}

function updateLoopUi() {
    const btn = elLoop();
    if (!btn) return;
    btn.dataset.mode = loopMode;
    btn.setAttribute(
        'aria-label',
        loopMode === 'off' ? 'Enable loop' : loopMode === 'one' ? 'Loop: one song' : 'Loop: all'
    );
    emit();
}

// ── Audio element listeners ─────────────────────────────────────────────

audio.addEventListener('timeupdate', updateScrubber);
audio.addEventListener('play', updatePlayIcon);
audio.addEventListener('pause', updatePlayIcon);
audio.addEventListener('ended', handleEnded);

audio.addEventListener('loadedmetadata', () => {
    elTime().textContent = `0:00 / ${formatTime(audio.duration)}`;
});

/**
 * loopMode 'one' replays; otherwise advances the queue (wrapping if
 * loopMode 'all'); if loopMode 'off' at the end of the queue, playback
 * stops but the player bar stays visible (Sprint 4 decision — bar only
 * hides on song deletion).
 */
function handleEnded() {
    if (loopMode === 'one') {
        audio.currentTime = 0;
        audio.play().catch(() => { });
        return;
    }

    if (queueIndex < queue.length - 1) {
        queueIndex += 1;
        playCurrentQueueEntry();
        return;
    }

    if (loopMode === 'all' && queue.length > 0) {
        queueIndex = 0;
        playCurrentQueueEntry();
        return;
    }

    updatePlayIcon();
    const scrubber = elScrubber();
    if (scrubber) scrubber.value = 0;
    elTime().textContent = `0:00 / ${formatTime(audio.duration)}`;
}

// ── Core load/play ───────────────────────────────────────────────────────

/**
 * Load and play a song directly, with no queue context.
 * Only plays if status === 'done'. Prefer `setQueueAndPlay` from app.js
 * so prev/next/shuffle/loop have a queue to operate on.
 * @param {{ id: string, title: string, channel: string, thumbnail_url: string|null, status: string, effective_duration: number|null }} song
 */
export function loadSong(song) {
    if (song.status !== 'done') return;
    currentSong = song;

    audio.src = `/api/songs/${song.id}/stream`;
    audio.play().catch(err => console.error('[player] play() failed', err));

    elBar().classList.remove('player-bar--empty');
    elThumb().src = song.thumbnail_url ?? '';
    elThumb().alt = song.title ?? '';
    elTitle().textContent = song.title ?? 'Unknown';
    elChannel().textContent = song.channel ?? '';

    const scrubber = elScrubber();
    if (scrubber) scrubber.value = 0;
    elTime().textContent = `0:00 / ${formatTime(song.effective_duration ?? song.duration ?? 0)}`;
    emit();
}

function playCurrentQueueEntry() {
    const song = queue[queueIndex];
    if (song) loadSong(song);
}

// ── Queue (FE-1) ─────────────────────────────────────────────────────────

/**
 * Set the queue to a page's currently visible song list and play the
 * clicked song. Only 'done' songs are playable — non-done entries stay
 * in the queue (so positions/prev/next line up with the visible list)
 * but are skipped over by advance/prev.
 * @param {object[]} songList
 * @param {string} songId
 */
export function setQueueAndPlay(songList, songId) {
    queue = songList.slice();
    queueIndex = queue.findIndex(s => s.id === songId);
    if (queueIndex === -1) return;

    if (shuffle) shuffleQueueKeepingCurrent();

    playCurrentQueueEntry();
}

function fisherYates(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
}

function shuffleQueueKeepingCurrent() {
    const currentId = queue[queueIndex]?.id;
    fisherYates(queue);
    if (currentId) queueIndex = queue.findIndex(s => s.id === currentId);
}

export function toggleShuffle() {
    shuffle = !shuffle;
    if (shuffle && queue.length > 0) shuffleQueueKeepingCurrent();
    updateShuffleUi();
    return shuffle;
}

export function isShuffleOn() {
    return shuffle;
}

export function cycleLoopMode() {
    loopMode = loopMode === 'off' ? 'one' : loopMode === 'one' ? 'all' : 'off';
    localStorage.setItem('melo:loop', loopMode);
    updateLoopUi();
    return loopMode;
}

export function getLoopMode() {
    return loopMode;
}

function findNextPlayableIndex(from, step) {
    for (let i = from; i >= 0 && i < queue.length; i += step) {
        if (queue[i]?.status === 'done') return i;
    }
    return -1;
}

/** Next button — independent of autoplay/loop-one; does not wrap. */
export function next() {
    const nextIdx = findNextPlayableIndex(queueIndex + 1, 1);
    if (nextIdx === -1) return;
    queueIndex = nextIdx;
    playCurrentQueueEntry();
}

/** Previous button — restarts current song if already at queue start. */
export function prev() {
    if (audio.currentTime > 3) {
        audio.currentTime = 0;
        return;
    }
    const prevIdx = findNextPlayableIndex(queueIndex - 1, -1);
    if (prevIdx === -1) {
        audio.currentTime = 0;
        return;
    }
    queueIndex = prevIdx;
    playCurrentQueueEntry();
}

// ── Transport ────────────────────────────────────────────────────────────

export function play() {
    if (audio.src) audio.play().catch(() => { });
}

export function pause() {
    audio.pause();
}

export function togglePlayPause() {
    audio.paused ? play() : pause();
}

export function getCurrentSongId() {
    return currentSong?.id ?? null;
}

/** `@returns` {typeof currentSong} */
export function getCurrentSong() {
    return currentSong;
}

export function isPlayingSong(id) {
    return currentSong?.id === id && !audio.paused;
}

export function isSongLoaded(id) {
    return currentSong?.id === id;
}

/**
 * Seek to a percentage of the current song's duration. Used by the
 * Now Playing panel's scrubber (main player-bar scrubber uses its own
 * internal bindScrubber wiring instead).
 * @param {number} percent 0–100
 */
export function seekTo(percent) {
    if (!audio.duration || isNaN(audio.duration)) return;
    audio.currentTime = (clamp(percent, 0, 100) / 100) * audio.duration;
}


// ── Volume ───────────────────────────────────────────────────────────────

export function setVolume(v) {
    audio.volume = clamp(v, 0, 1);
    if (audio.volume > 0) preMuteVolume = audio.volume;
    localStorage.setItem('melo:volume', String(audio.volume));
    updateVolumeUi();
}

export function toggleMute() {
    if (audio.volume > 0) {
        preMuteVolume = audio.volume;
        setVolume(0);
    } else {
        setVolume(preMuteVolume || 1.0);
    }
}

// ── Now Playing panel subscription (FE-3) ───────────────────────────────

const listeners = new Set();

function emit() {
    listeners.forEach(fn => fn({
        song: currentSong,
        paused: audio.paused,
        currentTime: audio.currentTime,
        duration: audio.duration,
        volume: audio.volume,
        shuffle,
        loopMode,
    }));
}

/** Subscribe to player state changes. Returns an unsubscribe fn. */
export function subscribe(fn) {
    listeners.add(fn);
    fn({
        song: currentSong, paused: audio.paused, currentTime: audio.currentTime,
        duration: audio.duration, volume: audio.volume, shuffle, loopMode
    });
    return () => listeners.delete(fn);
}

// ── Waveform peaks (FE-3) ────────────────────────────────────────────────

const PEAK_BUCKETS = 200;
const peaksCache = new Map(); // songId -> Float32Array, in-memory only, session-scoped
let sharedAudioCtx = null;

function getAudioCtx() {
    if (!sharedAudioCtx) sharedAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return sharedAudioCtx;
}

function downsamplePeaks(channelData, buckets) {
    const blockSize = Math.floor(channelData.length / buckets);
    const peaks = new Float32Array(buckets);
    for (let i = 0; i < buckets; i++) {
        const start = i * blockSize;
        let max = 0;
        for (let j = 0; j < blockSize; j++) {
            const v = Math.abs(channelData[start + j] ?? 0);
            if (v > max) max = v;
        }
        peaks[i] = max;
    }
    return peaks;
}

/**
 * Fetch + decode a song's audio once, cache peaks in-memory for the
 * session (cleared on reload, no persistence — FE-3 spec).
 * @param {string} songId
 * @returns {Promise<Float32Array>}
 */
export async function getPeaks(songId) {
    if (peaksCache.has(songId)) return peaksCache.get(songId);

    const res = await fetch(`/api/songs/${songId}/stream`);
    if (!res.ok) throw new Error('Failed to fetch audio for waveform');
    const arrayBuffer = await res.arrayBuffer();
    const audioBuffer = await getAudioCtx().decodeAudioData(arrayBuffer);
    const peaks = downsamplePeaks(audioBuffer.getChannelData(0), PEAK_BUCKETS);

    peaksCache.set(songId, peaks);
    return peaks;
}


// ── Bind controls — call once after DOM ready ───────────────────────────

export function bindPlayerControls() {
    bindScrubber();

    document.getElementById('btn-play-pause')?.addEventListener('click', togglePlayPause);
    elPrev()?.addEventListener('click', prev);
    elNext()?.addEventListener('click', next);
    elShuffle()?.addEventListener('click', toggleShuffle);
    elLoop()?.addEventListener('click', cycleLoopMode);

    elVolumeBtn()?.addEventListener('click', toggleMute);
    elVolumeSlider()?.addEventListener('input', e => setVolume(parseFloat(e.target.value)));

    updateVolumeUi();
    updateShuffleUi();
    updateLoopUi();
}

function bindScrubber() {
    const scrubber = elScrubber();
    if (!scrubber) return;

    // While dragging, stop timeupdate from fighting the scrubber
    scrubber.addEventListener('mousedown', () => { isSeeking = true; });

    scrubber.addEventListener('input', () => {
        if (!audio.duration || isNaN(audio.duration)) return;
        const seekTo = (scrubber.value / 100) * audio.duration;
        elTime().textContent = `${formatTime(seekTo)} / ${formatTime(audio.duration)}`;
    });

    scrubber.addEventListener('change', () => {
        if (!audio.duration || isNaN(audio.duration)) return;
        audio.currentTime = (scrubber.value / 100) * audio.duration;
        isSeeking = false;
    });

    scrubber.addEventListener('mouseup', () => { isSeeking = false; });
}
