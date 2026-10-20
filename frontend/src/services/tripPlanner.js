import axios from './protectedRequest';
import { backendAuthConfig } from './backendAuth';
import { getFreshRoutingAlgorithm } from './routingSettings';
import { getSession, isCurrentSession, SessionError } from './session';
import { preferenceWeights, roomInputs } from '../pages/TripSetup/setupModel';

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

export async function planStructuredRoute(draft, origin, destination, signal) {
  const started = getSession();
  const { data: initial_route } = await axios.get(
    import.meta.env.VITE_BACKEND_SERVER + 'get-initial-route',
    {
      ...backendAuthConfig(),
      signal,
      params: {
        start_lat: origin.latitude,
        start_lon: origin.longitude,
        end_lat: destination.latitude,
        end_lon: destination.longitude,
      },
    }
  );
  const algorithm = await getFreshRoutingAlgorithm();
  if (!isCurrentSession(started) || signal.aborted) throw new SessionError('session-changed');
  const payload = {
    initial_route,
    ...structuredTripInputs(draft),
    ...(algorithm ? { algorithm } : {}),
  };
  const { data: route } = await axios.post(
    import.meta.env.VITE_BACKEND_SERVER + 'generate-final-route',
    payload,
    { ...backendAuthConfig(), signal }
  );
  if (
    !route ||
    !Array.isArray(route.coordinates) ||
    route.coordinates.length < 2 ||
    !route.geometry ||
    !Number.isFinite(route.distance) ||
    !Number.isFinite(route.duration)
  )
    throw new Error('The planning service did not return a complete route.');
  return route;
}

export async function planStructuredItinerary(route, signal) {
  const { data } = await axios.post(
    import.meta.env.VITE_BACKEND_SERVER + 'generate-itinerary',
    { route },
    { ...backendAuthConfig(), signal }
  );
  if (!Array.isArray(data) || !data.length) throw new Error('No completed itinerary was returned.');
  return data;
}
