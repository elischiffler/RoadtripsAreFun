import request from './protectedRequest';
import { validStopCoordinates } from './tripPresentation';

/** Sample the actual GeoJSON route, converting [longitude, latitude] at this boundary only. */
export function alternativeRequest(route) {
  const geometry = (route?.geometry?.coordinates || [])
    .map((point) => (Array.isArray(point) ? [point[1], point[0]] : null))
    .filter(validStopCoordinates);
  const available = geometry.length
    ? geometry
    : (route?.stops || []).map((stop) => stop?.coordinates).filter(validStopCoordinates);
  const unique = [...new Map(available.map((point) => [point.join(','), point])).values()];
  const count = Math.min(8, unique.length);
  const points = Array.from(
    { length: count },
    (_, index) => unique[Math.round((index * (unique.length - 1)) / Math.max(1, count - 1))]
  );
  const exclude_ids = [
    ...new Set(
      (route?.stops || [])
        .map((stop) => stop?.provider_id || stop?.id)
        .filter((id) => typeof id === 'string')
    ),
  ].slice(0, 100);
  return { points, exclude_ids };
}

export async function loadRouteAlternatives(route, signal) {
  const body = alternativeRequest(route);
  if (!body.points.length) throw new Error('This route has no locations to search around.');
  const response = await request.post(
    `${import.meta.env.VITE_BACKEND_SERVER}route-alternatives`,
    body,
    { signal }
  );
  if (!Array.isArray(response.data?.places))
    throw new Error('Nearby suggestions are unavailable. Please retry.');
  return {
    places: response.data.places.filter(
      (place) =>
        place &&
        typeof place.id === 'string' &&
        typeof place.name === 'string' &&
        validStopCoordinates(place.coordinates)
    ),
    notice: typeof response.data.notice === 'string' ? response.data.notice : '',
  };
}
