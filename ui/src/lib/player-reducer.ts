// ui/src/lib/player-reducer.ts
// Pure state-transition logic for PlayerProvider, ported from player.js's
// queue/shuffle/loop functions. No <audio> access, no localStorage — those
// are the provider's job (side effects live there, not here).

import { findNextPlayableIndex } from "./queue";
import { shuffleKeepingCurrent, restoreOriginalOrder } from "./shuffle";
import { cycleLoopMode, type LoopMode } from "./loop-mode";
import type { Song } from "./types";

export interface PlayerState {
  queue: Song[];
  originalQueue: Song[];
  queueIndex: number;
  shuffle: boolean;
  loopMode: LoopMode;
}

export const initialPlayerState: PlayerState = {
  queue: [],
  originalQueue: [],
  queueIndex: -1,
  shuffle: false,
  loopMode: "off",
};

export type PlayerAction =
  | { type: "SET_QUEUE"; queue: Song[]; songId: string }
  | { type: "TOGGLE_SHUFFLE" }
  | { type: "CYCLE_LOOP" }
  | { type: "NEXT" }
  | { type: "PREV" }
  | { type: "ENDED" };

export function playerReducer(
  state: PlayerState,
  action: PlayerAction,
): PlayerState {
  switch (action.type) {
    case "SET_QUEUE": {
      const index = action.queue.findIndex((s) => s.id === action.songId);
      if (index === -1) return state;
      const base = {
        ...state,
        queue: action.queue,
        originalQueue: action.queue,
        queueIndex: index,
      };
      if (!state.shuffle) return base;
      const { queue, index: shuffledIndex } = shuffleKeepingCurrent(
        action.queue,
        index,
      );
      return { ...base, queue, queueIndex: shuffledIndex };
    }
    case "TOGGLE_SHUFFLE": {
      if (!state.shuffle) {
        const { queue, index } = shuffleKeepingCurrent(
          state.queue,
          state.queueIndex,
        );
        return { ...state, shuffle: true, queue, queueIndex: index };
      }
      const { queue, index } = restoreOriginalOrder(
        state.queue,
        state.originalQueue,
        state.queueIndex,
      );
      return { ...state, shuffle: false, queue, queueIndex: index };
    }
    case "CYCLE_LOOP":
      return { ...state, loopMode: cycleLoopMode(state.loopMode) };
    case "NEXT": {
      const idx = findNextPlayableIndex(state.queue, state.queueIndex + 1, 1);
      return idx === -1 ? state : { ...state, queueIndex: idx };
    }
    case "PREV": {
      const idx = findNextPlayableIndex(state.queue, state.queueIndex - 1, -1);
      return idx === -1 ? state : { ...state, queueIndex: idx };
    }
    case "ENDED": {
      const idx = findNextPlayableIndex(state.queue, state.queueIndex + 1, 1);
      if (idx !== -1) return { ...state, queueIndex: idx };
      if (state.loopMode === "all") {
        const first = findNextPlayableIndex(state.queue, 0, 1);
        if (first !== -1) return { ...state, queueIndex: first };
      }
      return state;
    }
    default:
      return state;
  }
}
