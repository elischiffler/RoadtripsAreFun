import { dailyScheduleFromRhythm, supportsOvernightRhythm } from './dailyRhythm';
import { validStopCoordinates } from '../../services/tripPresentation';

const line = (route) =>
  Array.isArray(route?.geometry?.coordinates) &&
  route.geometry.coordinates.length >= 2 &&
  route.geometry.coordinates.length <= 10000 &&
  route.geometry.coordinates.every(
    (point) =>
      Array.isArray(point) && point.length === 2 && validStopCoordinates([point[1], point[0]])
  );

/** Road-only rest regions are a draft map hint, never hotel inventory or a quote. */
export function approximateRestRegions(route, draft) {
  if (
    !line(route) ||
    !Number.isFinite(route.duration) ||
    route.duration <= 0 ||
    !draft.dailyRhythm ||
    !supportsOvernightRhythm(draft.dailyRhythm)
  )
    return [];
  let slots;
  try {
    slots = dailyScheduleFromRhythm(draft.dailyRhythm).slots;
  } catch {
    return [];
  }
  const [hour, minute] = draft.time.split(':').map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute) || slots[hour] !== 'drive') return [];
  let firstHours = 1 - minute / 60;
  for (let next = (hour + 1) % 24; slots[next] === 'drive'; next = (next + 1) % 24) firstHours += 1;
  const dailyHours = slots.filter((slot) => slot === 'drive').length;
  const points = route.geometry.coordinates;
  const lengths = points.slice(1).map((b, index) => {
    const a = points[index],
      toRadians = Math.PI / 180;
    const dLat = (b[1] - a[1]) * toRadians,
      dLon = (b[0] - a[0]) * toRadians;
    const half =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(a[1] * toRadians) * Math.cos(b[1] * toRadians) * Math.sin(dLon / 2) ** 2;
    return 2 * Math.asin(Math.sqrt(Math.min(1, half)));
  });
  const total = lengths.reduce((sum, value) => sum + value, 0);
  if (!total) return [];
  const regions = [];
  for (
    let seconds = firstHours * 3600;
    seconds < route.duration && regions.length < 3;
    seconds += dailyHours * 3600
  ) {
    const target = (total * seconds) / route.duration;
    let elapsed = 0,
      edge = 0;
    while (edge < lengths.length - 1 && elapsed + lengths[edge] < target)
      elapsed += lengths[edge++];
    const fraction = lengths[edge] ? Math.min(1, (target - elapsed) / lengths[edge]) : 0;
    const a = points[edge],
      b = points[edge + 1];
    let delta = b[0] - a[0];
    if (delta > 180) delta -= 360;
    if (delta < -180) delta += 360;
    const longitude = ((a[0] + delta * fraction + 540) % 360) - 180;
    regions.push({
      coordinates: [a[1] + (b[1] - a[1]) * fraction, longitude],
      label: 'Possible rest region',
      approximate: true,
    });
  }
  return regions;
}
