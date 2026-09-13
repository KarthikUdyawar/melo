// ui/src/lib/queue.ts
// Ported from player.js's findNextPlayableIndex() — pure fn, no queue
// mutation, no <audio> access. Never wraps (queue.js's next()/prev()
// callers decide wrap behavior themselves per loopMode).

import type { Song } from "./types";

export function findNextPlayableIndex(
  queue: Song[],
  from: number,
  step: 1 | -1,
): number {
  for (let i = from; i >= 0 && i < queue.length; i += step) {
    if (queue[i]?.status === "done") return i;
  }
  return -1;
}
