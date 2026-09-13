// ui/src/lib/waveform-cache.ts
// Session-scoped peaks cache, ported from player.js's module-scope
// peaksCache — survives panel close/reopen, no persistence. Kept as a
// separate module (not inside PlayerProvider) so it isn't tied to the
// provider's own lifecycle/re-renders.
//
// AudioContext.decodeAudioData() itself stays untested here — jsdom has
// no Web Audio — see waveform.test.ts for the tested downsample math.

import { downsamplePeaks } from "./waveform";

const PEAK_BUCKETS = 200;
const peaksCache = new Map<string, Promise<Float32Array>>();
let sharedAudioCtx: AudioContext | null = null;

function getAudioCtx(): AudioContext {
  if (!sharedAudioCtx) sharedAudioCtx = new AudioContext();
  return sharedAudioCtx;
}

/** Fetch + decode a song's audio once; cache peaks for the session. */
export function getPeaks(
  songId: string,
  signal?: AbortSignal,
): Promise<Float32Array> {
  const cached = peaksCache.get(songId);
  if (cached) return cached;

  const pending = (async () => {
    const res = await fetch(`/api/songs/${songId}/stream`, { signal });
    if (!res.ok) throw new Error("Failed to fetch audio for waveform");
    const arrayBuffer = await res.arrayBuffer();
    const audioBuffer = await getAudioCtx().decodeAudioData(arrayBuffer);
    return downsamplePeaks(audioBuffer.getChannelData(0), PEAK_BUCKETS);
  })().catch((err) => {
    if (peaksCache.get(songId) === pending) peaksCache.delete(songId);
    throw err;
  });

  peaksCache.set(songId, pending);
  return pending;
}
