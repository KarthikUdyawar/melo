// ui/src/lib/shuffle.test.ts
import { shuffleKeepingCurrent, restoreOriginalOrder } from "./shuffle";
import type { Song } from "./types";

const mk = (id: string): Song => ({
  id,
  title: null,
  youtube_id: null,
  file_url: null,
  duration: null,
  start: null,
  end: null,
  speed: 1.0,
  status: "done",
  thumbnail_url: null,
  channel: null,
  upload_date: null,
  created_at: "",
  is_favorite: false,
  stream_url: "",
  effective_duration: null,
});

test("shuffled queue keeps the current song at its (new) found index, same id", () => {
  const queue = [mk("a"), mk("b"), mk("c"), mk("d"), mk("e")];
  const { queue: shuffled, index } = shuffleKeepingCurrent(queue, 2); // "c" is current
  expect(shuffled[index]?.id).toBe("c");
});

test("shuffled queue preserves the same set of ids", () => {
  const queue = [mk("a"), mk("b"), mk("c"), mk("d")];
  const { queue: shuffled } = shuffleKeepingCurrent(queue, 0);
  expect(shuffled.map((s) => s.id).sort()).toEqual(["a", "b", "c", "d"]);
});

test("shuffle does not mutate the input array", () => {
  const queue = [mk("a"), mk("b"), mk("c")];
  const original = queue.slice();
  shuffleKeepingCurrent(queue, 1);
  expect(queue).toEqual(original);
});

test("restoreOriginalOrder returns the exact original array", () => {
  const original = [mk("a"), mk("b"), mk("c")];
  const shuffled = [mk("c"), mk("a"), mk("b")];
  const { queue: restored } = restoreOriginalOrder(shuffled, original, 0); // "c" current in shuffled
  expect(restored).toEqual(original);
});

test("restoreOriginalOrder finds current song's new index in original order", () => {
  const original = [mk("a"), mk("b"), mk("c")];
  const shuffled = [mk("c"), mk("a"), mk("b")];
  const { index } = restoreOriginalOrder(shuffled, original, 0); // shuffled[0] = "c"
  expect(index).toBe(2); // "c" is at index 2 in original
});

test("restoreOriginalOrder returns -1 index if current song id no longer present", () => {
  const original = [mk("a"), mk("b")];
  const shuffled = [mk("x"), mk("a")];
  const { index } = restoreOriginalOrder(shuffled, original, 0);
  expect(index).toBe(-1);
});

test("shuffleKeepingCurrent returns -1 index when currentIndex is out of bounds", () => {
  const queue = [mk("a"), mk("b"), mk("c")];
  const { index } = shuffleKeepingCurrent(queue, 99); // queue[99] is undefined
  expect(index).toBe(-1);
});
