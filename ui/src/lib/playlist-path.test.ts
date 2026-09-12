import { parsePlaylistId } from "./playlist-path";

test("extracts id with trailing slash", () => {
  expect(parsePlaylistId("/playlists/abc123/")).toBe("abc123");
});

test("extracts id without trailing slash", () => {
  expect(parsePlaylistId("/playlists/abc123")).toBe("abc123");
});

test("build-time placeholder shell resolves to null", () => {
  expect(parsePlaylistId("/playlists/_/")).toBeNull();
});

test("non-matching paths resolve to null", () => {
  expect(parsePlaylistId("/playlists/")).toBeNull();
  expect(parsePlaylistId("/")).toBeNull();
  expect(parsePlaylistId("/favorites")).toBeNull();
});