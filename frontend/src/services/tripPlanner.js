import axios from './protectedRequest';
import { backendAuthConfig } from './backendAuth';
import { getFreshRoutingAlgorithm } from './routingSettings';
import { getSession, isCurrentSession, SessionError } from './session';
import { preferenceWeights, roomInputs } from '../pages/TripSetup/setupModel';
import { streamTripRoute } from './tripRouteStream';

export function plannerError(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ');
  if (error instanceof SessionError) return error.message;
  return 'The planning service could not finish. Your draft is kept. Please try again.';
}

const validLocation = (value) =>
  value &&
  typeof value.address === 'string' &&
  value.address.trim() &&
  Number.isFinite(value.latitude) &&
  Number.isFinite(value.longitude) &&
  Math.abs(value.latitude) <= 90 &&
  Math.abs(value.longitude) <= 180;

export async function resolveTripLocation(address, signal) {
  let candidates;
  try {
    const { data } = await axios.post(
      import.meta.env.VITE_BACKEND_SERVER + 'validate-location',
      { is_coordinates: false, location: { address } },
      { ...backendAuthConfig(), signal }
    );
    candidates = [data];
  } catch (error) {
    if (error.response?.status !== 409) throw error;
    candidates = error.response?.data?.detail?.candidates;
  }
  if (
    !Array.isArray(candidates) ||
    !candidates.length ||
    candidates.some((item) => !validLocation(item))
  )
    throw new Error('No usable address match was returned. Please refine the city or address.');
  return candidates.map(({ address: label, latitude, longitude }) => ({
    address: label,
    latitude,
    longitude,
  }));
}

export function structuredTripInputs(draft) {
  return {
    num_stops: Number(draft.stops),
    budget: Number(draft.budget),
    traveler_count: Number(draft.travelers),
    hotel_rooms: roomInputs(draft),
    persona_weights: preferenceWeights(draft),
    scheduling_policy: { ...draft.schedule },
    // The retained API localizes this wall time using the origin's provider timezone.
    // Never apply the browser's timezone or invent a UTC offset.
    start: draft.date + 'T' + draft.time + ':00',
  };
}

const validCoordinates = (points, latitudeFirst = false) =>
  Array.isArray(points) &&
  points.length >= 2 &&
  points.every(
    (point) =>
      Array.isArray(point) &&
      point.length === 2 &&
      point.every(Number.isFinite) &&
      Math.abs(point[latitudeFirst ? 0 : 1]) <= 90 &&
      Math.abs(point[latitudeFirst ? 1 : 0]) <= 180
  );

export async function estimateStructuredRoute(origin, destination, signal) {
  const { data } = await axios.get(import.meta.env.VITE_BACKEND_SERVER + 'get-initial-route', {
    ...backendAuthConfig(),
    signal,
    params: {
      start_lat: origin.latitude,
      start_lon: origin.longitude,
      end_lat: destination.latitude,
      end_lon: destination.longitude,
    },
  });
  if (
    !data ||
    !Number.isFinite(data.duration) ||
    data.duration < 0 ||
    !Number.isFinite(data.distance) ||
    data.distance < 0 ||
    !validCoordinates(data.geometry?.coordinates)
  )
    throw new Error('A usable driving estimate was not returned.');
  return data;
}

export async function planStructuredRoute(
  draft,
  origin,
  destination,
  signal,
  { onProgress, reserveMealSlots = false } = {}
) {
  const started = getSession();
  let initial_route;
  if (onProgress) {
    initial_route = await estimateStructuredRoute(origin, destination, signal);
    onProgress({ type: 'progress', stage: 'route.initial', state: 'completed' });
  } else {
    // Keep the ordinary four-argument API compatible with existing callers.
    const response = await axios.get(import.meta.env.VITE_BACKEND_SERVER + 'get-initial-route', {
      ...backendAuthConfig(),
      signal,
      params: {
        start_lat: origin.latitude,
        start_lon: origin.longitude,
        end_lat: destination.latitude,
        end_lon: destination.longitude,
      },
    });
    initial_route = response.data;
  }
  const algorithm = await getFreshRoutingAlgorithm();
  if (!isCurrentSession(started) || signal?.aborted) throw new SessionError('session-changed');
  const payload = {
    initial_route,
    ...structuredTripInputs(draft),
    ...(reserveMealSlots ? { reserve_meal_slots: true } : {}),
    ...(algorithm ? { algorithm } : {}),
  };
  let route;
  if (onProgress) route = await streamTripRoute(payload, signal, onProgress);
  else {
    const response = await axios.post(
      import.meta.env.VITE_BACKEND_SERVER + 'generate-final-route',
      payload,
      { ...backendAuthConfig(), signal }
    );
    route = response.data;
  }
  if (
    !route ||
    !validCoordinates(route.coordinates, true) ||
    !validCoordinates(route.geometry?.coordinates) ||
    !Number.isFinite(route.distance) ||
    route.distance < 0 ||
    !Number.isFinite(route.duration) ||
    route.duration < 0
  )
    throw new Error('The planning service did not return a complete route.');
  if (reserveMealSlots && route.reserve_meal_slots !== true)
    throw new Error('The planning service did not confirm meal breaks. Your draft is kept.');
  return route;
}

export async function planStructuredItinerary(route, signal, { includeMealSlots = false } = {}) {
  const { data } = await axios.post(
    import.meta.env.VITE_BACKEND_SERVER + 'generate-itinerary',
    { route, ...(includeMealSlots ? { include_meal_slots: true } : {}) },
    { ...backendAuthConfig(), signal }
  );
  if (!Array.isArray(data) || !data.length) throw new Error('No completed itinerary was returned.');
  return data;
}
