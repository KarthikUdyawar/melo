"use client";

// ui/src/components/PlayerBar.tsx
// Ported from index.html's player-bar markup + player.js's scrubber/volume
// binding (FE7-6). Info area opens the Now Playing panel — Enter/Space
// accessible, same as the vanilla #player-info-trigger.

import { useState } from "react";
import { usePlayer } from "./PlayerProvider";
import { formatDuration } from "@/lib/format";
import { NowPlayingPanel } from "./NowPlayingPanel";
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

export function PlayerBar() {
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

  const [npOpen, setNpOpen] = useState(false);

  if (!currentSong) {
    return (
      <div className="player-bar player-bar--empty" id="player-bar">
        <div className="player-bar__placeholder">
          <span>No song playing — pick one from your library</span>
        </div>
      </div>
    );
  }

  const progressPct = duration ? (currentTime / duration) * 100 : 0;
  const muted = volume === 0;

  return (
    <>
      <div className="player-bar" id="player-bar">
        <div
          className="player-bar__info"
          id="player-info-trigger"
          role="button"
          tabIndex={0}
          onClick={() => setNpOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setNpOpen(true);
            }
          }}
        >
          {currentSong.thumbnail_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              className="player-bar__thumb"
              src={currentSong.thumbnail_url}
              alt=""
            />
          )}
          <div className="player-bar__meta">
            <div className="player-bar__title">
              {currentSong.title ?? "Unknown"}
            </div>
            <div className="player-bar__channel">
              {currentSong.channel ?? ""}
            </div>
          </div>
        </div>

        <button
          className="icon-btn"
          aria-pressed={shuffle}
          aria-label="Shuffle"
          onClick={toggleShuffle}
        >
          <ShuffleIcon />
        </button>

        <div className="player-ctrl-wide">
          <button aria-label="Previous" onClick={prev}>
            <PrevIcon />
          </button>
          <button
            aria-label={paused ? "Play" : "Pause"}
            onClick={togglePlayPause}
          >
            {paused ? <PlayIcon /> : <PauseIcon />}
          </button>
          <button aria-label="Next" onClick={next}>
            <NextIcon />
          </button>

          <input
            className="player-scrubber"
            type="range"
            min={0}
            max={100}
            value={progressPct}
            style={{ "--progress": `${progressPct}%` } as React.CSSProperties}
            onChange={(e) => seek((Number(e.target.value) / 100) * duration)}
            aria-label="Seek"
          />
          <span className="player-bar__time">
            {formatDuration(currentTime)} / {formatDuration(duration)}
          </span>
        </div>

        <button
          className="loop-btn icon-btn"
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

        <div className="player-volume">
          <button
            aria-label={muted ? "Unmute" : "Mute"}
            onClick={() => setVolume(muted ? 1.0 : 0)}
          >
            {muted ? <MuteIcon /> : <VolumeIcon />}
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
      <NowPlayingPanel isOpen={npOpen} onClose={() => setNpOpen(false)} />
    </>
  );
}
