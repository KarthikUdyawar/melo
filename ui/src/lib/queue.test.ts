// ui/src/lib/queue.test.ts
import { findNextPlayableIndex } from "./queue";
import type { Song } from "./types";

const entry = (status: Song["status"]): Song => ({
  id: status + Math.random(),
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

test("finds next done entry forward", () => {
  const q = [entry("done"), entry("pending"), entry("done")];
  expect(findNextPlayableIndex(q, 1, 1)).toBe(2);
});

test("finds next done entry backward", () => {
  const q = [entry("done"), entry("pending"), entry("done")];
  expect(findNextPlayableIndex(q, 1, -1)).toBe(0);
});

test("skips multiple non-done entries", () => {
  const q = [
    entry("done"),
    entry("pending"),
    entry("processing"),
    entry("failed"),
    entry("done"),
  ];
  expect(findNextPlayableIndex(q, 1, 1)).toBe(4);
});

test("returns -1 when nothing playable ahead", () => {
  const q = [entry("done"), entry("pending"), entry("pending")];
  expect(findNextPlayableIndex(q, 1, 1)).toBe(-1);
});

test("returns -1 when starting index is out of bounds", () => {
  const q = [entry("done")];
  expect(findNextPlayableIndex(q, 5, 1)).toBe(-1);
  expect(findNextPlayableIndex(q, -1, -1)).toBe(-1);
});

test("does not wrap — stops at array end", () => {
  const q = [entry("pending"), entry("pending")];
  expect(findNextPlayableIndex(q, 0, 1)).toBe(-1);
});
