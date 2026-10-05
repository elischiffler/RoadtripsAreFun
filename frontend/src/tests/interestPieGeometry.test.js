import { describe, expect, it } from 'vitest';
import {
  HANDLE_WIDTH,
  HANDLE_HEIGHT,
  layoutHandles,
} from '../pages/AlgorithmLab/interestPieGeometry';
const slices = (sizes) => {
  let start = 0;
  return sizes.map((size, index) => {
    const slice = { key: String(index), start, size };
    start += size;
    return slice;
  });
};
// Independently check actual rectangular hit-target edges/containment rather
// than reusing the placement algorithm's separating-axis test.
const corners = (handle) => {
  const angle = ((handle.start + handle.size) * Math.PI) / 50;
  return [
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ].map(([x, y]) => [
    handle.x +
      ((x * HANDLE_WIDTH) / 2) * Math.cos(angle) -
      ((y * HANDLE_HEIGHT) / 2) * Math.sin(angle),
    handle.y +
      ((x * HANDLE_WIDTH) / 2) * Math.sin(angle) +
      ((y * HANDLE_HEIGHT) / 2) * Math.cos(angle),
  ]);
};
const cross = (a, b, p) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
function collides(a, b) {
  const contains = (polygon, point) =>
    polygon.every((p, i) => cross(p, polygon[(i + 1) % 4], point) >= 0);
  if (contains(a, b[0]) || contains(b, a[0])) return true;
  return a.some((p, i) =>
    b.some((q, j) => {
      const r = a[(i + 1) % 4],
        s = b[(j + 1) % 4];
      return cross(p, r, q) * cross(p, r, s) < 0 && cross(q, s, p) * cross(q, s, r) < 0;
    })
  );
}
function expectSeparated(sizes) {
  const handles = layoutHandles(slices(sizes));
  expect(handles).toHaveLength(sizes.length);
  for (let i = 0; i < handles.length; i++) {
    for (let j = i + 1; j < handles.length; j++) {
      expect(collides(corners(handles[i]), corners(handles[j])), `handles ${i} and ${j}`).toBe(
        false
      );
    }
  }
  return handles;
}
describe('pie handle collisions', () => {
  it('keeps ordinary handles on the rim', () => {
    expect(expectSeparated([25, 25, 25, 25]).map((h) => h.radius)).toEqual([113, 113, 113, 113]);
  });
  it('separates fourteen minimum-sized topics and preserves every handle', () => {
    const handles = expectSeparated(Array(14).fill(1));
    expect(new Set(handles.map((h) => h.radius)).size).toBeGreaterThan(1);
  });
  it('detects neighboring handles across the 100% / 0% seam', () => {
    expectSeparated([...Array(13).fill(1), 87]);
    expectSeparated([1, 87, ...Array(12).fill(1)]);
    expectSeparated([87, ...Array(13).fill(1)]);
  });
});
