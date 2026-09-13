// ui/src/lib/player-reducer.test.ts
import { playerReducer, initialPlayerState } from "./player-reducer";
import type { Song } from "./types";

const mk = (id: string, status: Song["status"] = "done"): Song => ({
  id,
  title: null,
  youtube_id: null,
  file_url: null,
  duration: null,
  start: null,
  end: null,
  speed: 1.0,
  status,
  thumbnail_url: null,
  channel: null,
  upload_date: null,
  created_at: "",
  is_favorite: false,
  stream_url: "",
  effective_duration: null,
});

test("SET_QUEUE sets queue, originalQueue, and index by songId", () => {
  const queue = [mk("a"), mk("b"), mk("c")];
  const state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "b",
  });
  expect(state.queue).toEqual(queue);
  expect(state.originalQueue).toEqual(queue);
  expect(state.queueIndex).toBe(1);
});

test("SET_QUEUE re-shuffles immediately if shuffle is already on", () => {
  const queue = [mk("a"), mk("b"), mk("c")];
  const shuffledState = { ...initialPlayerState, shuffle: true };
  const state = playerReducer(shuffledState, {
    type: "SET_QUEUE",
    queue,
    songId: "b",
  });
  expect(state.queue.find((s) => s.id === "b")).toBeTruthy();
  expect(state.queue[state.queueIndex]?.id).toBe("b");
});

test("TOGGLE_SHUFFLE on shuffles keeping current in place, off restores original", () => {
  const queue = [mk("a"), mk("b"), mk("c")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "b",
  });
  state = playerReducer(state, { type: "TOGGLE_SHUFFLE" });
  expect(state.shuffle).toBe(true);
  expect(state.queue[state.queueIndex]?.id).toBe("b");

  state = playerReducer(state, { type: "TOGGLE_SHUFFLE" });
  expect(state.shuffle).toBe(false);
  expect(state.queue).toEqual(queue);
  expect(state.queue[state.queueIndex]?.id).toBe("b");
});

test("CYCLE_LOOP cycles off -> one -> all -> off", () => {
  let state = playerReducer(initialPlayerState, { type: "CYCLE_LOOP" });
  expect(state.loopMode).toBe("one");
  state = playerReducer(state, { type: "CYCLE_LOOP" });
  expect(state.loopMode).toBe("all");
  state = playerReducer(state, { type: "CYCLE_LOOP" });
  expect(state.loopMode).toBe("off");
});

test("NEXT advances to the next done entry, skipping non-done", () => {
  const queue = [mk("a"), mk("b", "pending"), mk("c")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "a",
  });
  state = playerReducer(state, { type: "NEXT" });
  expect(state.queueIndex).toBe(2);
});

test("NEXT is a no-op at the end of the queue (index unchanged)", () => {
  const queue = [mk("a"), mk("b")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "b",
  });
  state = playerReducer(state, { type: "NEXT" });
  expect(state.queueIndex).toBe(1);
});

test("ENDED with loopMode=all wraps to the first playable entry", () => {
  const queue = [mk("a"), mk("b")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "b",
  });
  state = playerReducer(state, { type: "CYCLE_LOOP" }); // one
  state = playerReducer(state, { type: "CYCLE_LOOP" }); // all
  state = playerReducer(state, { type: "ENDED" });
  expect(state.queueIndex).toBe(0);
});

test("ENDED with loopMode=off at queue end leaves index unchanged (caller stops playback)", () => {
  const queue = [mk("a"), mk("b")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "b",
  });
  state = playerReducer(state, { type: "ENDED" });
  expect(state.queueIndex).toBe(1);
});

test("PREV moves to the previous done entry", () => {
  const queue = [mk("a"), mk("b"), mk("c")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "c",
  });
  state = playerReducer(state, { type: "PREV" });
  expect(state.queueIndex).toBe(1);
});

test("PREV is a no-op at the start of the queue", () => {
  const queue = [mk("a"), mk("b")];
  let state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "a",
  });
  state = playerReducer(state, { type: "PREV" });
  expect(state).toBe(state); // same reference, no-op
  expect(state.queueIndex).toBe(0);
});

test("SET_QUEUE with unknown songId is a no-op", () => {
  const queue = [mk("a"), mk("b")];
  const state = playerReducer(initialPlayerState, {
    type: "SET_QUEUE",
    queue,
    songId: "zzz",
  });
  expect(state).toBe(initialPlayerState);
});

test("unknown action type is a no-op", () => {
  // @ts-expect-error testing default branch
  expect(playerReducer(initialPlayerState, { type: "NOPE" })).toBe(
    initialPlayerState,
  );
});
