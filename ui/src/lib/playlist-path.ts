/**
 * Extracts the real playlist id from the URL path. The build only emits
 * a placeholder shell at /playlists/_/ (static export can't know real
 * ids at build time); nginx rewrites real /playlists/<uuid>/ requests
 * to that shell while leaving the address bar untouched — so the real
 * id must be read from window.location.pathname client-side, not from
 * Next's route params. See DECISIONS.md Sprint 7.
 */
export function parsePlaylistId(pathname: string): string | null {
  const match = pathname.match(/^\/playlists\/([^/]+)\/?$/);
  if (!match) return null;
  return match[1] === "_" ? null : match[1];
}