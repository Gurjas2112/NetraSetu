import { describe, expect, it } from "vitest";
import { grayLaplacianVariance, ringScore } from "./laplacian";

function image(width: number, height: number, pixel: (x: number, y: number) => number): ImageData {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const v = pixel(x, y);
      const o = (y * width + x) * 4;
      data[o] = v;
      data[o + 1] = v;
      data[o + 2] = v;
      data[o + 3] = 255;
    }
  }
  return { width, height, data, colorSpace: "srgb" } as ImageData;
}

describe("quality ring laplacian", () => {
  it("is near zero on a flat field and higher on a checkerboard", () => {
    const flat = image(16, 16, () => 128);
    const check = image(16, 16, (x, y) => ((x + y) % 2 === 0 ? 0 : 255));
    expect(grayLaplacianVariance(flat)).toBeLessThan(1e-6);
    expect(grayLaplacianVariance(check)).toBeGreaterThan(grayLaplacianVariance(flat));
    expect(ringScore(0)).toBe(0);
    expect(ringScore(1)).toBe(1);
  });
});
