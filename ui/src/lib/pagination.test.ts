import { hasMorePages } from "./pagination";

test("bookmark present and full page -> more pages", () => {
  expect(hasMorePages("abc", 50, 50)).toBe(true);
});

test("bookmark present but short page -> no more pages", () => {
  expect(hasMorePages("abc", 12, 50)).toBe(false);
});

test("no bookmark -> no more pages regardless of length", () => {
  expect(hasMorePages(null, 50, 50)).toBe(false);
});