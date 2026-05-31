/**
 * player.js — Single <audio> element. Persists across hash navigation.
 */

const audio = document.createElement('audio');
audio.preload = 'none';
document.body.appendChild(audio);

let currentSong = null;
let isSeeking = false;

const elBar = () => document.getElementById('player-bar');
const elThumb = () => document.getElementById('player-thumb');
const elTitle = () => document.getElementById('player-title');
const elChannel = () => document.getElementById('player-channel');
const elScrubber = () => document.getElementById('player-scrubber');
const elTime = () => document.getElementById('player-time');
const elPlay = () => document.getElementById('icon-play');
const elPause = () => document.getElementById('icon-pause');

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function updatePlayIcon() {
    elPlay().style.display = audio.paused ? '' : 'none';
    elPause().style.display = audio.paused ? 'none' : '';
}

function updateScrubber() {
    if (isSeeking) return;
    const scrubber = elScrubber();
    if (!scrubber || !audio.duration || isNaN(audio.duration)) return;
    scrubber.value = (audio.currentTime / audio.duration) * 100;
    elTime().textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
}

audio.addEventListener('timeupdate', updateScrubber);
audio.addEventListener('play', updatePlayIcon);
audio.addEventListener('pause', updatePlayIcon);
audio.addEventListener('ended', () => {
    updatePlayIcon();
    const scrubber = elScrubber();
    if (scrubber) scrubber.value = 0;
    elTime().textContent = `0:00 / ${formatTime(audio.duration)}`;
});

audio.addEventListener('loadedmetadata', () => {
    elTime().textContent = `0:00 / ${formatTime(audio.duration)}`;
});

/**
 * Load and play a song. Only plays if status === 'done'.
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
}

export function play() {
    if (audio.src) audio.play().catch(() => { });
}

export function pause() {
    audio.pause();
}

export function togglePlayPause() {
    audio.paused ? play() : pause();
}

/** @returns {typeof currentSong} */
export function getCurrentSong() {
    return currentSong;
}

export function isPlayingSong(id) {
    return currentSong?.id === id && !audio.paused;
}

export function isSongLoaded(id) {
    return currentSong?.id === id;
}

/** Wire scrubber — call once after DOM ready */
export function bindScrubber() {
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

document.getElementById('btn-play-pause')
    ?.addEventListener('click', togglePlayPause);
