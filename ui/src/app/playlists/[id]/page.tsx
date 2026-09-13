// ui/src/app/playlists/[id]/page.tsx

// Server Component shell — only job is generateStaticParams (must live
// in a Server Component, can't combine with "use client"). Real render
// logic + pathname parsing moved to PlaylistDetailClient.

import { PlaylistDetailClient } from "./PlaylistDetailClient";

/**
 * Static export needs a build-time-known param; the real id is unknown
 * until runtime, so this shell is the only page emitted. nginx rewrites
 * any real /playlists/<uuid>/ request to this shell's index.html — see
 * next.config.mjs's `output: 'export'` and DECISIONS.md Sprint 7.
 */
export function generateStaticParams() {
  return [{ id: "_" }];
}

export default function PlaylistDetailPage() {
  return <PlaylistDetailClient />;
}
