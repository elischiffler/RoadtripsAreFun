import { alternativeRequest } from './routeAlternatives';
import { streamRoutePreparation } from './tripRouteStream';
import { validStopCoordinates } from './tripPresentation';
import { schedulingPolicyFromDraft } from '../pages/TripSetup/dailyRhythm';

/** Known road geometry only. Text input never becomes invented map positions. */
export function preparationRequest(route, draft) {
  if (!route || !draft || !/^([01]\d|2[0-3]):[0-5]\d$/.test(draft.time ?? '')) return null;
  if (!Number.isFinite(route.duration) || route.duration < 0 || route.duration > 63 * 86400)
    return null;
  try {
    const { geometry } = alternativeRequest(route);
    if (!geometry) return null;
    return {
      geometry,
      driving_seconds: route.duration,
      departure_clock: draft.time,
      scheduling_policy: schedulingPolicyFromDraft(draft),
    };
  } catch {
    return null;
  }
}

export const preparationPlaces = (places) =>
  (Array.isArray(places) ? places : [])
    .filter(
      (p) =>
        typeof p?.id === 'string' &&
        typeof p.name === 'string' &&
        validStopCoordinates(p.coordinates)
    )
    .slice(0, 12);

export const tentativeAreas = (areas) =>
  (Array.isArray(areas) ? areas : [])
    .filter(
      (a) =>
        typeof a?.id === 'string' &&
        typeof a.label === 'string' &&
        validStopCoordinates(a.coordinates) &&
        a.tentative === true &&
        a.hotel_quotes_checked === false &&
        a.availability_checked === false &&
        a.clock_basis === 'departure_wall_clock_estimate'
    )
    .slice(0, 3);

export const loadRoutePreparation = (payload, signal, onProgress) =>
  streamRoutePreparation(payload, signal, onProgress);
