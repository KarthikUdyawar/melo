// ui/src/lib/shuffle.ts
// Ported from player.js's shuffleQueueKeepingCurrent()/restoreOriginalOrder().
// Pure — takes queue + current index, returns a new queue + new index.
// Caller (PlayerProvider) owns originalQueue/queue/queueIndex state.

import type { Song } from "./types";

function fisherYates<T>(arr: T[]): T[] {
  const copy = arr.slice();
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j]!, copy[i]!];
  }
  return copy;
}

export function shuffleKeepingCurrent(
  queue: Song[],
  currentIndex: number,
): { queue: Song[]; index: number } {
  const currentId = queue[currentIndex]?.id;
  const shuffled = fisherYates(queue);
  const index = currentId ? shuffled.findIndex((s) => s.id === currentId) : -1;
  return { queue: shuffled, index };
}

export function restoreOriginalOrder(
  queue: Song[],
  originalQueue: Song[],
  currentIndex: number,
): { queue: Song[]; index: number } {
  const currentId = queue[currentIndex]?.id;
  const restored = originalQueue.slice();
  const index = currentId ? restored.findIndex((s) => s.id === currentId) : -1;
  return { queue: restored, index };
}
