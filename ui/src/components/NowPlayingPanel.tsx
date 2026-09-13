"use client";

// ui/src/components/NowPlayingPanel.tsx
// Full-screen overlay, ported from app.js's buildNowPlayingHtml +
// drawWaveform (FE7-6, rest of it). Mirrors PlayerBar state live via
// usePlayer() — doesn't own its own timers, same rule the old
// subscribe() pub-sub followed.
//
// Own independent scrubber drag-state (npSeeking) — mirrors PlayerBar's
// but isn't shared, same reasoning as the vanilla version (two scrubbers
// can't share one seeking flag without one interrupting the other).

import { useEffect, useRef, useState } from "react";
import { usePlayer } from "./PlayerProvider";
import { getPeaks } from "@/lib/waveform-cache";
import { formatDuration } from "@/lib/format";
import { trapFocus } from "@/lib/focus-trap";
import {
  ShuffleIcon,
  PrevIcon,
  PlayIcon,
  PauseIcon,
  NextIcon,
  LoopIcon,
  VolumeIcon,
  MuteIcon,
} from "./icons";

interface NowPlayingPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NowPlayingPanel({ isOpen, onClose }: NowPlayingPanelProps) {
  const {
    currentSong,
    paused,
    shuffle,
    loopMode,
    volume,
    currentTime,
    duration,
    next,
    prev,
    togglePlayPause,
    toggleShuffle,
    cycleLoop,
    setVolume,
    seek,
  } = usePlayer();

  const panelRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [peaks, setPeaks] = useState<Float32Array | null>(null);
  const [npSeeking, setNpSeeking] = useState(false);
  const [dragPct, setDragPct] = useState(0);

  // Focus in on open, restore to trigger on close (trigger re-focuses
  // itself via PlayerBar's onClose handler, not here).
  useEffect(() => {
    if (isOpen) closeBtnRef.current?.focus();
  }, [isOpen]);

  // Fetch + decode waveform once per song, aborted on song switch/close.
  useEffect(() => {
    if (!isOpen || !currentSong) return;
    setPeaks(null);
    const controller = new AbortController();
    getPeaks(currentSong.id, controller.signal)
      .then(setPeaks)
      .catch(() => {
        /* visual-only, silent fail — no toast noise */
      });
    return () => controller.abort();
  }, [isOpen, currentSong]);

  // Redraw on every tick to color played/unplayed bars.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !peaks) return;
    drawWaveform(canvas, peaks, duration ? currentTime / duration : 0);
  }, [peaks, currentTime, duration]);

  if (!isOpen || !currentSong) return null;

  const progressPct = npSeeking
    ? dragPct
    : duration
      ? (currentTime / duration) * 100
      : 0;
  const displayTime =
    npSeeking && duration ? (dragPct / 100) * duration : currentTime;

  const commitSeek = () => {
    if (!npSeeking || !duration) return;
    seek((dragPct / 100) * duration);
    setNpSeeking(false);
  };

  return (
    <div
      className="now-playing-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="now-playing"
        role="dialog"
        aria-modal="true"
        aria-label="Now playing"
        ref={panelRef}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose();
            return;
          }
          if (panelRef.current) trapFocus(panelRef.current, e.nativeEvent);
        }}
      >
        <button
          ref={closeBtnRef}
          className="icon-btn now-playing__close"
          aria-label="Close"
          onClick={onClose}
        >
          ✕
        </button>
        {currentSong.thumbnail_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            className="now-playing__thumb"
            src={currentSong.thumbnail_url}
            alt=""
          />
        )}
        <div className="now-playing__title">{currentSong.title ?? ""}</div>
        <div className="now-playing__channel">{currentSong.channel ?? ""}</div>

        <canvas ref={canvasRef} className="now-playing__canvas" />

        <div className="now-playing__transport">
          <button
            className="player-btn"
            aria-pressed={shuffle}
            aria-label="Shuffle"
            onClick={toggleShuffle}
          >
            <ShuffleIcon />
          </button>
          <button className="player-btn" aria-label="Previous" onClick={prev}>
            <PrevIcon />
          </button>
          <button
            className="player-btn"
            aria-label={paused ? "Play" : "Pause"}
            onClick={togglePlayPause}
          >
            {paused ? <PlayIcon /> : <PauseIcon />}
          </button>
          <button className="player-btn" aria-label="Next" onClick={next}>
            <NextIcon />
          </button>
          <button
            className="player-btn loop-btn"
            data-mode={loopMode}
            aria-label={
              loopMode === "off"
                ? "Enable loop"
                : loopMode === "one"
                  ? "Loop: one song"
                  : "Loop: all"
            }
            onClick={cycleLoop}
          >
            <LoopIcon />
            <span className="loop-badge" aria-hidden="true">
              1
            </span>
          </button>
        </div>

        <input
          type="range"
          className="player-scrubber"
          min={0}
          max={100}
          value={progressPct}
          style={{ "--progress": `${progressPct}%` } as React.CSSProperties}
          onMouseDown={() => setNpSeeking(true)}
          onTouchStart={() => setNpSeeking(true)}
          onChange={(e) => setDragPct(Number(e.target.value))}
          onMouseUp={commitSeek}
          onTouchEnd={commitSeek}
          aria-label="Seek"
        />
        <span className="player-time">
          {formatDuration(displayTime)} / {formatDuration(duration)}
        </span>

        <div className="player-volume">
          <button
            aria-label={volume === 0 ? "Unmute" : "Mute"}
            onClick={() => setVolume(volume === 0 ? 1.0 : 0)}
          >
            {volume === 0 ? <MuteIcon /> : <VolumeIcon />}
          </button>
          <input
            className="volume-slider"
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            style={{ "--progress": `${volume * 100}%` } as React.CSSProperties}
            onChange={(e) => setVolume(Number(e.target.value))}
            aria-label="Volume"
          />
        </div>
      </div>
    </div>
  );
}

/** Ported from app.js's drawWaveform — barWidth clamped so it can't go
 *  negative when peak count exceeds canvas width (Post-Sprint-6 fix). */
function drawWaveform(
  canvas: HTMLCanvasElement,
  peaks: Float32Array,
  progress: number,
) {
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * dpr;
  canvas.height = height * dpr;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  const style = getComputedStyle(document.documentElement);
  const playedColor = style.getPropertyValue("--accent").trim() || "#c8f04e";
  const unplayedColor =
    style.getPropertyValue("--bg-elevated").trim() || "#1f1f1f";

  function drawBar(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
  ) {
    const r = Math.min(w / 2, 2);
    const ctxAny = ctx as CanvasRenderingContext2D & {
      roundRect?: (
        x: number,
        y: number,
        w: number,
        h: number,
        r: number,
      ) => void;
    };
    if (typeof ctxAny.roundRect === "function") {
      ctx.beginPath();
      ctxAny.roundRect(x, y, w, h, r);
      ctx.fill();
    } else {
      ctx.fillRect(x, y, w, h);
    }
  }

  const slot = width / peaks.length;
  const barGap = Math.min(2, slot / 2);
  const barWidth = Math.max(1, slot - barGap);
  const mid = height / 2;
  const playedBars = Math.floor(peaks.length * progress);

  peaks.forEach((peak, i) => {
    const barHeight = Math.max(2, peak * height);
    const x = i * (barWidth + barGap);
    ctx.fillStyle = i < playedBars ? playedColor : unplayedColor;
    drawBar(ctx, x, mid - barHeight / 2, barWidth, barHeight);
  });
}
