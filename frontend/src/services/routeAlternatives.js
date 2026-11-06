import request from './protectedRequest';
import { validStopCoordinates } from './tripPresentation';

/** Preserve the full GeoJSON line; the backend samples it by distance. */
export function alternativeRequest(route) {
  const rawGeometry = route?.geometry?.coordinates;
  const geometry = Array.isArray(rawGeometry) && rawGeometry.length ? rawGeometry : null;
  if (geometry && (geometry.length > 10000 || geometry.length < 2))
    throw new Error('This route geometry cannot be searched.');
  if (
    geometry &&
    geometry.some(
      (point) =>
        !Array.isArray(point) || point.length !== 2 || !validStopCoordinates([point[1], point[0]])
    )
  )
    throw new Error('This route has invalid geometry.');
  const stops = route?.stops || [];
  const exclude_coordinates = [
    ...new Map(
      stops
        .map((stop) => stop?.coordinates)
        .filter(validStopCoordinates)
        .map((point) => [point.join(','), point])
    ).values(),
  ];
  const exclude_ids = [
    ...new Set(
      stops
        .flatMap((stop) => [stop?.provider_id, stop?.id])
        .filter((id) => typeof id === 'string' && id.length)
    ),
  ];
  if (exclude_coordinates.length > 100 || exclude_ids.length > 100)
    throw new Error('This route has too many stops to search safely.');
  if (geometry) return { geometry, exclude_ids, exclude_coordinates };
  // Legacy saved routes without geometry can only search their known stop positions.
  const points = exclude_coordinates.slice(0, 8);
  return { points, exclude_ids, exclude_coordinates };
}

export async function loadRouteAlternatives(route, signal) {
  const body = alternativeRequest(route);
  if (!body.geometry?.length && !body.points?.length)
    throw new Error('This route has no locations to search around.');
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
    ...(response.data.coverage ? { coverage: response.data.coverage } : {}),
  };
}
