// ui/src/lib/loop-mode.ts
// Ported from player.js's cycleLoopMode() — pure state transition only.
// Persistence (localStorage['melo:loop']) is the caller's job (FE7-4's
// PlayerProvider), not this function's — keeps it a pure fn, no I/O.

export type LoopMode = "off" | "one" | "all";

const NEXT: Record<LoopMode, LoopMode> = {
  off: "one",
  one: "all",
  all: "off",
};

export const cycleLoopMode = (mode: LoopMode): LoopMode => NEXT[mode];
