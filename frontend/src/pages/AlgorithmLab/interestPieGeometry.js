// SVG-space dimensions also size the CSS hit targets, so collision spacing scales
// with the chart on smaller screens. Half a unit of clearance surrounds each grip.
export const HANDLE_WIDTH = 8;
export const HANDLE_HEIGHT = 20;
export function piePoint(percent, radius = 110) {
  const angle = (percent / 100) * Math.PI * 2 - Math.PI / 2;
  return [140 + radius * Math.cos(angle), 140 + radius * Math.sin(angle)];
}

function overlaps(a, b) {
  const delta = [b.x - a.x, b.y - a.y];
  const dot = (u, v) => u[0] * v[0] + u[1] * v[1];
  const extent = (handle, axis) =>
    Math.abs(dot(handle.tangent, axis)) * (HANDLE_WIDTH / 2 + 0.5) +
    Math.abs(dot(handle.radial, axis)) * (HANDLE_HEIGHT / 2 + 0.5);
  // Separating-axis test for rotated rectangles, including the circular seam.
  return [...a.axes, ...b.axes].every(
    (axis) => Math.abs(dot(delta, axis)) < extent(a, axis) + extent(b, axis)
  );
}

export function layoutHandles(slices) {
  const placed = [];
  for (const slice of slices) {
    const percent = slice.start + slice.size;
    const angle = (percent / 100) * Math.PI * 2;
    const radial = [Math.sin(angle), -Math.cos(angle)];
    const tangent = [Math.cos(angle), Math.sin(angle)];
    for (const radius of [113, 87, 61, 35]) {
      const [x, y] = piePoint(percent, radius);
      const handle = { ...slice, x, y, radius, radial, tangent, axes: [radial, tangent] };
      if (placed.every((other) => !overlaps(handle, other))) {
        placed.push(handle);
        break;
      }
    }
  }
  return placed;
}
