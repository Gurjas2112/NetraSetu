/** Cheap focus proxy for the live quality ring (~5 fps on a downscaled canvas). */

export function grayLaplacianVariance(image: ImageData): number {
  const { width, height, data } = image;
  if (width < 3 || height < 3) return 0;
  const gray = new Float32Array(width * height);
  for (let i = 0; i < gray.length; i += 1) {
    const o = i * 4;
    const r = data[o] ?? 0;
    const g = data[o + 1] ?? 0;
    const b = data[o + 2] ?? 0;
    gray[i] = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  }
  let n = 0;
  let sum = 0;
  let sumSq = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x;
      const v =
        -4 * (gray[i] ?? 0) +
        (gray[i - 1] ?? 0) +
        (gray[i + 1] ?? 0) +
        (gray[i - width] ?? 0) +
        (gray[i + width] ?? 0);
      n += 1;
      sum += v;
      sumSq += v * v;
    }
  }
  if (n === 0) return 0;
  const mean = sum / n;
  return Math.max(0, sumSq / n - mean * mean);
}

/** Maps Laplacian variance on a 128×128 canvas into a 0–1 ring fill. Not a clinical threshold. */
export function ringScore(lapVar: number): number {
  return Math.max(0, Math.min(1, lapVar / 0.015));
}
