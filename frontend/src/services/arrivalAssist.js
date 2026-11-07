import { itineraryEntries, validStopCoordinates, visitedStopIds } from './tripPresentation';

// Conservative foreground hints, not proof of entry or a completed visit.
export const ARRIVAL_LIMITS = Object.freeze({
  radiusMeters: 150,
  departureMeters: 200,
  accuracyMeters: 50,
  maxAgeMs: 15000,
  futureToleranceMs: 2000,
  dwellMs: 45000,
  maxGapMs: 15000,
  maxDriftMeters: 50,
  maxSpeedMetersPerSecond: 2.5,
});
const MINUTE = 60000;
const timestamp = (value) =>
  typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : NaN;

export function distanceMeters(a, b) {
  const radians = (value) => (value * Math.PI) / 180;
  const lat = radians(b[0] - a[0]);
  const lon = radians(b[1] - a[1]);
  const h =
    Math.sin(lat / 2) ** 2 +
    Math.cos(radians(a[0])) * Math.cos(radians(b[0])) * Math.sin(lon / 2) ** 2;
  return 6371008.8 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}

export function nextArrivalTarget(trip) {
  const visited = visitedStopIds(trip.presentation);
  const next = itineraryEntries(trip.itinerary)
    .flatMap((day) => day.stops)
    .find(
      ({ id, stop }) =>
        stop.type === 'stop' && stop.kind === 'arrival' && !stop.optional && !visited.has(id)
    );
  if (!next?.stop.provider_id) return null;
  const matches = (trip.route?.stops || []).filter(
    (stop) =>
      stop.type === 'stop' &&
      stop.provider_id === next.stop.provider_id &&
      stop.arrival_time === next.stop.arrival_time
  );
  if (matches.length !== 1 || !validStopCoordinates(matches[0].coordinates)) return null;
  const stop = matches[0];
  const departure = timestamp(trip.route.departure_time);
  const arrival = timestamp(stop.arrival_time);
  const leaving = timestamp(stop.departure_time);
  if (![departure, arrival, leaving].every(Number.isFinite) || leaving < arrival) return null;
  return {
    id: next.id,
    name: stop.name,
    coordinates: stop.coordinates,
    earliest: Math.max(departure - 15 * MINUTE, arrival - 60 * MINUTE),
    latest: leaving + 6 * 60 * MINUTE,
  };
}

export function createArrivalTracker() {
  let evidence = null;
  let lastTimestamp = -Infinity;
  let lastArrival = null;
  const detected = new Set();
  const reset = (reason) => {
    evidence = null;
    return { state: 'waiting', reason };
  };
  return {
    observe(position, target, now = Date.now()) {
      if (!target || detected.has(target.id)) return reset('target');
      if (now < target.earliest || now > target.latest) return reset('schedule');
      const { latitude, longitude, accuracy, speed } = position?.coords || {};
      const point = [latitude, longitude];
      const acquired = position?.timestamp;
      if (
        !Number.isFinite(now) ||
        !Number.isFinite(acquired) ||
        acquired <= lastTimestamp ||
        now - acquired > ARRIVAL_LIMITS.maxAgeMs ||
        acquired - now > ARRIVAL_LIMITS.futureToleranceMs
      )
        return reset('freshness');
      lastTimestamp = acquired;
      if (
        !validStopCoordinates(point) ||
        !Number.isFinite(accuracy) ||
        accuracy < 0 ||
        accuracy > ARRIVAL_LIMITS.accuracyMeters
      )
        return reset('accuracy');
      if (
        speed != null &&
        (!Number.isFinite(speed) || speed < 0 || speed > ARRIVAL_LIMITS.maxSpeedMetersPerSecond)
      )
        return reset('moving');
      if (lastArrival && !lastArrival.exited) {
        if (
          distanceMeters(point, lastArrival.coordinates) - accuracy <
          ARRIVAL_LIMITS.departureMeters
        )
          return reset('departure');
        lastArrival.exited = true;
      }
      if (distanceMeters(point, target.coordinates) + accuracy > ARRIVAL_LIMITS.radiusMeters)
        return reset('distance');
      if (
        !evidence ||
        evidence.id !== target.id ||
        now < evidence.received ||
        now - evidence.received > ARRIVAL_LIMITS.maxGapMs ||
        acquired - evidence.acquired > ARRIVAL_LIMITS.maxGapMs ||
        distanceMeters(point, evidence.anchor) > ARRIVAL_LIMITS.maxDriftMeters
      ) {
        evidence = {
          id: target.id,
          anchor: point,
          first: now,
          firstAcquired: acquired,
          received: now,
          acquired,
          samples: 1,
        };
      } else {
        evidence.received = now;
        evidence.acquired = acquired;
        evidence.samples++;
      }
      if (
        evidence.samples >= 3 &&
        now - evidence.first >= ARRIVAL_LIMITS.dwellMs &&
        acquired - evidence.firstAcquired >= ARRIVAL_LIMITS.dwellMs
      ) {
        detected.add(target.id);
        lastArrival = { coordinates: [...target.coordinates], exited: false };
        evidence = null;
        return { state: 'arrived', id: target.id, name: target.name };
      }
      return { state: 'waiting', reason: 'dwell' };
    },
    reset() {
      evidence = null;
    },
  };
}
