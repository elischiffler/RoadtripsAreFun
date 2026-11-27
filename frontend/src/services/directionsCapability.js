export const appleDirectionsHeader = { 'X-Roadtrips-Directions': 'apple' };

export function directionsCapability(url) {
  const api = import.meta.env.VITE_BACKEND_SERVER;
  if (!api || !url.startsWith(api)) return {};
  const path = url.slice(api.length).split('?')[0];
  return /^(?:get-initial-route|generate-final-route(?:\/stream)?|route-directions|studio\/(?:run|runs|jobs|route-directions)(?:\/.*)?|algorithm-lab\/(?:run|runs)(?:\/.*)?)$/.test(
    path
  )
    ? appleDirectionsHeader
    : {};
}

export const isAppleRoute = (route) => route?.directions_provider === 'apple';

const roadFields = new Set([
  'geometry',
  'distance',
  'duration',
  'steps',
  'legs',
  'road_distance',
  'drive_seconds',
  'driving_duration',
  'provider_response',
  'route_summary',
  'one_day_proof',
]);

function withoutRoadData(value) {
  if (Array.isArray(value)) return value.map(withoutRoadData);
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !roadFields.has(key))
        .map(([key, item]) => [key, withoutRoadData(item)])
    );
  return value;
}

export function safeAppleSnapshot(snapshot) {
  if (
    !snapshot?.route ||
    (!isAppleRoute(snapshot.route) && snapshot.tripProfile?.apple_route_intent !== true)
  )
    return snapshot;
  return {
    ...snapshot,
    ...('initial' in snapshot ? { initial: null } : {}),
    route: { ...withoutRoadData(snapshot.route), directions_provider: 'apple' },
    itinerary: withoutRoadData(snapshot.itinerary),
  };
}
