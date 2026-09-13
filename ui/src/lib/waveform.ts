// ui/src/lib/waveform.ts
// Ported from player.js's downsamplePeaks() — pure math, no AudioContext/
// canvas (both unsupported in jsdom, see DECISIONS.md/PRD.md FE7-9). The
// AudioContext.decodeAudioData() call and <canvas> render stay untested
// at this layer, same gap Sprint 6 had for manual smoke.

export function downsamplePeaks(
  channelData: Float32Array,
  buckets: number,
): Float32Array {
  const blockSize = Math.floor(channelData.length / buckets);
  const peaks = new Float32Array(buckets);
  for (let i = 0; i < buckets; i++) {
    const start = i * blockSize;
    let sumSquares = 0;
    for (let j = 0; j < blockSize; j++) {
      const v = channelData[start + j] ?? 0;
      sumSquares += v * v;
    }
    const rms = Math.sqrt(sumSquares / blockSize);
    // sqrt again = perceptual compression, keeps quiet sections visible
    // instead of near-zero, natural wave shape rather than a flat block
    peaks[i] = Math.sqrt(rms);
  }
  return peaks;
}
