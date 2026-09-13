// ui/src/lib/waveform.test.ts
import { downsamplePeaks } from "./waveform";

test("downsamples to the requested bucket count", () => {
  const data = new Float32Array(1000).fill(0.5);
  const peaks = downsamplePeaks(data, 200);
  expect(peaks.length).toBe(200);
});

test("each bucket holds sqrt(RMS) of its block (perceptual, not peak)", () => {
  // 4 samples, 2 buckets -> block size 2
  const data = new Float32Array([0.1, -0.9, 0.3, 0.2]);
  const peaks = downsamplePeaks(data, 2);
  // bucket0: rms(0.1,-0.9) = sqrt((0.01+0.81)/2) = sqrt(0.41); peak = sqrt(rms)
  expect(peaks[0]).toBeCloseTo(0.8002, 3);
  // bucket1: rms(0.3,0.2) = sqrt((0.09+0.04)/2) = sqrt(0.065); peak = sqrt(rms)
  expect(peaks[1]).toBeCloseTo(0.5049, 3);
});

test("handles all-zero input", () => {
  const data = new Float32Array(100);
  const peaks = downsamplePeaks(data, 10);
  expect(Array.from(peaks)).toEqual(new Array(10).fill(0));
});

test("uneven division truncates remainder samples (matches player.js port)", () => {
  // 10 samples, 3 buckets -> blockSize = floor(10/3) = 3, last bucket ignores sample 9
  const data = new Float32Array([0, 0, 0, 0, 0, 0, 0, 0, 0, 5]);
  const peaks = downsamplePeaks(data, 3);
  expect(peaks[2]).toBe(0); // sample index 9 (the "5") falls outside blockSize*3=9 range
});
