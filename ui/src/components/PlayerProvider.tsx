"use client";

// ui/src/components/PlayerProvider.tsx
// React context replacing player.js's module-scope <audio> singleton.
// Mounted once in root layout.tsx (FE7-6) so the audio element survives
// route navigation — same guarantee the old singleton had.
//
// Untested at this layer (real <audio>/localStorage side effects) —
// pure logic already covered by player-reducer.test.ts / shuffle.test.ts /
// queue.test.ts / loop-mode.test.ts, per PRD's locked "logic-only tests"
// decision for this ticket.

import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useRef,
  useState,
} from "react";
import { playerReducer, initialPlayerState } from "@/lib/player-reducer";
import type { Song } from "@/lib/types";
import type { LoopMode } from "@/lib/loop-mode";
function readVolume(): number {
  const raw = parseFloat(localStorage.getItem("melo:volume") ?? "");
  return Number.isFinite(raw) ? Math.min(1, Math.max(0, raw)) : 1.0;
}

function readLoopMode(): LoopMode {
  const raw = localStorage.getItem("melo:loop");
  return raw === "one" || raw === "all" ? raw : "off";
}

interface PlayerContextValue {
  currentSong: Song | null;
  queue: Song[];
  queueIndex: number;
  shuffle: boolean;
  loopMode: LoopMode;
  paused: boolean;
  volume: number;
  currentTime: number;
  duration: number;
  setQueueAndPlay: (queue: Song[], songId: string) => void;
  next: () => void;
  prev: () => void;
  togglePlayPause: () => void;
  toggleShuffle: () => void;
  cycleLoop: () => void;
  setVolume: (v: number) => void;
  seek: (time: number) => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const loadedSongIdRef = useRef<string | null>(null);
  const [state, dispatch] = useReducer(playerReducer, initialPlayerState);
  const [paused, setPaused] = useState(true);
  const [volume, setVolumeState] = useState(1.0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const volumePersistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = "none";
    audio.volume = readVolume();
    setVolumeState(audio.volume);
    audioRef.current = audio;

    const onPlay = () => setPaused(false);
    const onPause = () => setPaused(true);
    const onEnded = () => {
      if (readLoopMode() === "one") {
        audio.currentTime = 0;
        audio.play().catch(() => {});
        return;
      }
      dispatch({ type: "ENDED" });
    };
    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => setDuration(audio.duration || 0);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);

    return () => {
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.pause();
    };
  }, []);

  // Load whatever song the queue points at, whenever the index changes.
  useEffect(() => {
    const song = state.queue[state.queueIndex];
    const audio = audioRef.current;
    if (!song || !audio || song.status !== "done") return;
    // Shuffle rebuilds `queue` (new array reference) but keeps the same
    // song at queueIndex — guard on song id, not array/index identity,
    // so reshuffling doesn't restart playback from 0:00.
    if (loadedSongIdRef.current === song.id) return;
    loadedSongIdRef.current = song.id;
    audio.src = `/api/songs/${song.id}/stream`;
    audio.play().catch(() => {});
    setCurrentTime(0);
    setDuration(0);
  }, [state.queue, state.queueIndex]);

  const setQueueAndPlay = (queue: Song[], songId: string) =>
    dispatch({ type: "SET_QUEUE", queue, songId });

  const next = () => dispatch({ type: "NEXT" });

  const prev = () => {
    const audio = audioRef.current;
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    dispatch({ type: "PREV" });
  };

  const togglePlayPause = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.paused ? audio.play().catch(() => {}) : audio.pause();
  };

  const toggleShuffle = () => dispatch({ type: "TOGGLE_SHUFFLE" });
  const cycleLoop = () => dispatch({ type: "CYCLE_LOOP" });

  const setVolume = (v: number) => {
    const clamped = Math.min(1, Math.max(0, v));
    if (audioRef.current) audioRef.current.volume = clamped;
    setVolumeState(clamped);
    if (volumePersistTimer.current) clearTimeout(volumePersistTimer.current);
    volumePersistTimer.current = setTimeout(() => {
      localStorage.setItem("melo:volume", String(clamped));
    }, 300);
  };

  const seek = (time: number) => {
    const audio = audioRef.current;
    if (!audio || !audio.duration || isNaN(audio.duration)) return;
    audio.currentTime = Math.min(Math.max(time, 0), audio.duration);
    setCurrentTime(audio.currentTime);
  };

  useEffect(() => {
    localStorage.setItem("melo:loop", state.loopMode);
  }, [state.loopMode]);

  const value: PlayerContextValue = {
    currentSong: state.queue[state.queueIndex] ?? null,
    queue: state.queue,
    queueIndex: state.queueIndex,
    shuffle: state.shuffle,
    loopMode: state.loopMode,
    paused,
    volume,
    currentTime,
    duration,
    setQueueAndPlay,
    next,
    prev,
    togglePlayPause,
    toggleShuffle,
    cycleLoop,
    setVolume,
    seek,
  };

  return (
    <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>
  );
}

export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used within a PlayerProvider");
  return ctx;
}
