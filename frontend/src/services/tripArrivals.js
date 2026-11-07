import { itineraryEntries, validStopCoordinates, visitedStopIds } from './tripPresentation';

export const ARRIVAL_POLICY = Object.freeze({
  radiusMeters: 100,
  departureMeters: 200,
  maxAccuracyMeters: 35,
  maxAgeMs: 10000,
  maxSampleGapMs: 15000,
  dwellMs: 60000,
  minSamples: 4,
  maxDriftMeters: 50,
  maxSpeedMetersPerSecond: 2.5,
});
const MINUTE = 60000;
const timestamp = (value) =>
  typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : NaN;
export function distanceMeters(a, b) {
  const radians = (value) => (value * Math.PI) / 180;
  const lat = radians(b[0] - a[0]),
    lon = radians(b[1] - a[1]);
  const h =
    Math.sin(lat / 2) ** 2 +
    Math.cos(radians(a[0])) * Math.cos(radians(b[0])) * Math.sin(lon / 2) ** 2;
  return 6371008.8 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}

/** Only unique, dated route attraction identities authorize automatic arrivals. */
export function arrivalTargets(trip) {
  const departure = timestamp(trip.route?.departure_time);
  if (!Number.isFinite(departure)) return [];
  const targets = [];
  for (const { id, stop } of itineraryEntries(trip.itinerary).flatMap((day) => day.stops)) {
    if (stop.type !== 'stop' || stop.kind !== 'arrival' || stop.optional) continue;
    if (!stop.provider_id) return [];
    const matches = (trip.route?.stops || []).filter(
      (candidate) =>
        candidate?.type === 'stop' &&
        candidate.provider_id === stop.provider_id &&
        candidate.arrival_time === stop.arrival_time
    );
    if (matches.length !== 1 || !validStopCoordinates(matches[0].coordinates)) return [];
    const record = matches[0],
      arrival = timestamp(record.arrival_time),
      leaving = timestamp(record.departure_time);
    if (![arrival, leaving].every(Number.isFinite) || leaving < arrival) return [];
    targets.push({
      id,
      name: record.name,
      coordinates: record.coordinates,
      earliest: Math.max(departure - 15 * MINUTE, arrival - 60 * MINUTE),
      latest: leaving + 360 * MINUTE,
    });
  }
  return targets;
}
export function nextArrivalTarget(trip) {
  const excluded = new Set([
    ...visitedStopIds(trip.presentation),
    ...automaticArrivalExcludedStopIds(trip.presentation),
  ]);
  return arrivalTargets(trip).find((target) => !excluded.has(target.id)) || null;
}

/** One transient detector: no raw locations leave sample() or enter storage. */
export function createArrivalDetector(targets, policy = ARRIVAL_POLICY) {
  let pending = null,
    previous = null,
    lastArrival = null,
    lastTimestamp = -Infinity;
  const invalidTargets =
    !Array.isArray(targets) ||
    targets.some(
      (target) =>
        !target ||
        typeof target.id !== 'string' ||
        !validStopCoordinates(target.coordinates) ||
        !Number.isFinite(target.earliest) ||
        !Number.isFinite(target.latest) ||
        target.latest < target.earliest
    );
  const detected = new Set();
  const reset = () => {
    pending = null;
    previous = null;
  };
  const waiting = (status = 'waiting') => {
    reset();
    return { status };
  };
  return {
    reset,
    sample(fix, now, excluded = new Set()) {
      if (invalidTargets) return waiting('unavailable');
      const target = targets.find((item) => !excluded.has(item.id) && !detected.has(item.id));
      if (!target) return waiting('done');
      if (now < target.earliest || now > target.latest) return waiting('schedule');
      const point = [fix?.latitude, fix?.longitude];
      if (
        !Number.isFinite(now) ||
        !validStopCoordinates(point) ||
        !Number.isFinite(fix.accuracy) ||
        fix.accuracy < 0 ||
        fix.accuracy > policy.maxAccuracyMeters ||
        !Number.isFinite(fix.timestamp) ||
        fix.timestamp > now ||
        now - fix.timestamp > policy.maxAgeMs ||
        fix.timestamp <= lastTimestamp
      )
        return waiting();
      lastTimestamp = fix.timestamp;
      if (
        previous &&
        (fix.timestamp - previous.timestamp > policy.maxSampleGapMs ||
          now - previous.received > policy.maxSampleGapMs ||
          now < previous.received)
      )
        reset();
      const inferredSpeed = previous
        ? distanceMeters(previous.point, point) / ((fix.timestamp - previous.timestamp) / 1000)
        : 0;
      previous = { point, timestamp: fix.timestamp, received: now };
      if (
        (fix.speed != null &&
          (!Number.isFinite(fix.speed) ||
            fix.speed < 0 ||
            fix.speed > policy.maxSpeedMetersPerSecond)) ||
        inferredSpeed > policy.maxSpeedMetersPerSecond
      ) {
        pending = null;
        return { status: 'moving' };
      }
      if (lastArrival && !lastArrival.exited) {
        if (
          distanceMeters(point, lastArrival.coordinates) - fix.accuracy <
          policy.departureMeters
        ) {
          pending = null;
          return { status: 'departure' };
        }
        lastArrival.exited = true;
      }
      const nearby = targets
        .map((item) => ({ target: item, distance: distanceMeters(point, item.coordinates) }))
        .sort((a, b) => a.distance - b.distance);
      if (
        nearby[0]?.target.id !== target.id ||
        nearby[0].distance + fix.accuracy > policy.radiusMeters
      ) {
        pending = null;
        return { status: 'watching' };
      }
      if (nearby[1] && nearby[1].distance - nearby[0].distance <= 2 * fix.accuracy) {
        pending = null;
        return { status: 'ambiguous' };
      }
      if (
        pending?.id !== target.id ||
        distanceMeters(point, pending.anchor) > policy.maxDriftMeters
      )
        pending = {
          id: target.id,
          anchor: point,
          first: fix.timestamp,
          received: now,
          samples: 0,
          accuracy: 0,
        };
      pending.samples++;
      pending.accuracy = Math.max(pending.accuracy, fix.accuracy);
      const dwellMs = fix.timestamp - pending.first;
      if (
        dwellMs < policy.dwellMs ||
        now - pending.received < policy.dwellMs ||
        pending.samples < policy.minSamples
      )
        return { status: 'dwelling', name: target.name };
      const arrival = {
        stopId: target.id,
        occurredAt: new Date(fix.timestamp).toISOString(),
        dwellSeconds: Math.floor(dwellMs / 1000),
        accuracyMeters: Math.ceil(pending.accuracy),
      };
      detected.add(target.id);
      lastArrival = { coordinates: [...target.coordinates], exited: false };
      pending = null;
      return { status: 'arrived', name: target.name, arrival };
    },
  };
}

/** Versioned native-ready domain event: never include raw position or a trail. */
export function arrivalEvent(tripId, arrival, source = 'web-foreground') {
  return {
    schemaVersion: 1,
    type: 'trip.stop.arrived',
    eventId: `${tripId}:${arrival.stopId}:${arrival.occurredAt}`,
    tripId,
    stopId: arrival.stopId,
    occurredAt: arrival.occurredAt,
    source,
    ...(source === 'web-foreground'
      ? { dwellSeconds: arrival.dwellSeconds, accuracyMeters: arrival.accuracyMeters }
      : {}),
  };
}

export function recordArrival(presentation, event) {
  const visited = visitedStopIds(presentation);
  if (visited.has(event.stopId)) return presentation;
  visited.add(event.stopId);
  return {
    ...presentation,
    visitedStopIds: [...visited],
    arrivals: { ...presentation?.arrivals, [event.stopId]: event },
  };
}

export function correctArrival(presentation, tripId, stopId, now = Date.now()) {
  const visited = visitedStopIds(presentation);
  const suppressed = new Set(automaticArrivalExcludedStopIds(presentation));
  const arrivals = { ...presentation?.arrivals };
  if (visited.has(stopId)) {
    visited.delete(stopId);
    delete arrivals[stopId];
    suppressed.add(stopId);
  } else {
    visited.add(stopId);
    suppressed.delete(stopId);
    arrivals[stopId] = arrivalEvent(
      tripId,
      { stopId, occurredAt: new Date(now).toISOString() },
      'manual'
    );
  }
  return {
    ...presentation,
    visitedStopIds: [...visited],
    arrivals,
    automaticArrivalExcludedStopIds: [...suppressed],
  };
}

export function automaticArrivalExcludedStopIds(presentation) {
  return Array.isArray(presentation?.automaticArrivalExcludedStopIds)
    ? presentation.automaticArrivalExcludedStopIds.filter((id) => typeof id === 'string')
    : [];
}
