import { itineraryEntries, validStopCoordinates, visitedStopIds } from './tripPresentation';

// Conservative foreground defaults. A radius is not proof of a visit: require
// repeated fresh, accurate, slow fixes wholly within the radius for a full dwell.
export const ARRIVAL_POLICY = Object.freeze({
  radiusMeters: 100,
  maxAccuracyMeters: 35,
  maxAgeMs: 10000,
  maxSampleGapMs: 20000,
  dwellMs: 60000,
  minSamples: 4,
  maxSpeedMetersPerSecond: 2.5,
});

export function distanceMeters(a, b) {
  const radians = (value) => (value * Math.PI) / 180;
  const dLat = radians(b[0] - a[0]);
  const dLon = radians(b[1] - a[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(radians(a[0])) * Math.cos(radians(b[0])) * Math.sin(dLon / 2) ** 2;
  return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}

/** Saved stop coordinates are [latitude, longitude], never Mapbox geometry. */
export function arrivalTargets(trip) {
  const routeStops = (Array.isArray(trip.route?.stops) ? trip.route.stops : [])
    .filter(Boolean)
    .flatMap((stop) => [
      stop,
      ...(Array.isArray(stop.evening_suggestions) ? stop.evening_suggestions : []),
    ]);
  return itineraryEntries(trip.itinerary).flatMap(({ stops }) =>
    stops.flatMap(({ id, stop }) => {
      if (stop.paired_departure || stop.kind === 'departure') return [];
      let coordinates = stop.coordinates;
      if (!validStopCoordinates(coordinates)) {
        // The historical itinerary omits coordinates. Never infer a location
        // from the route geometry, stop order, or a fuzzy/name-only match.
        const matches = routeStops.filter((candidate) => {
          if (stop.provider_id) return candidate.provider_id === stop.provider_id;
          if (stop.id) return candidate.id === stop.id;
          return (
            stop.kind === 'arrival' &&
            candidate.name === stop.name &&
            candidate.type === stop.type &&
            (candidate.address || '') === (stop.address || '')
          );
        });
        const points = matches.map((item) => item.coordinates);
        if (
          !points.length ||
          !points.every(validStopCoordinates) ||
          !points.every((point) => point[0] === points[0][0] && point[1] === points[0][1])
        )
          return [];
        coordinates = points[0];
      }
      return [{ id, name: stop.name, coordinates }];
    })
  );
}

/** In-memory detector. Does not retain a trail or read/write browser storage. */
export function createArrivalDetector(targets, policy = ARRIVAL_POLICY) {
  let pending = null;
  let previous = null;
  let lastTimestamp = -Infinity;
  const reset = () => {
    pending = null;
    previous = null;
  };
  return {
    reset,
    sample(fix, now, excluded = new Set()) {
      const point = [fix?.latitude, fix?.longitude];
      if (
        !validStopCoordinates(point) ||
        !Number.isFinite(fix.accuracy) ||
        fix.accuracy < 0 ||
        fix.accuracy > policy.maxAccuracyMeters ||
        !Number.isFinite(fix.timestamp) ||
        fix.timestamp > now ||
        now - fix.timestamp > policy.maxAgeMs ||
        fix.timestamp <= lastTimestamp
      ) {
        reset();
        return { status: 'waiting' };
      }
      lastTimestamp = fix.timestamp;
      if (previous && fix.timestamp - previous.timestamp > policy.maxSampleGapMs) reset();
      const inferredSpeed = previous
        ? distanceMeters(previous.point, point) / ((fix.timestamp - previous.timestamp) / 1000)
        : 0;
      previous = { point, timestamp: fix.timestamp };
      if (
        (Number.isFinite(fix.speed) && fix.speed > policy.maxSpeedMetersPerSecond) ||
        inferredSpeed > policy.maxSpeedMetersPerSecond
      ) {
        pending = null;
        return { status: 'moving' };
      }
      // Resolve the nearest physical stop before excluding visited ones. Two
      // visits to the same place must not both complete during one dwell.
      const nearby = targets
        .map((target) => ({ target, distance: distanceMeters(point, target.coordinates) }))
        .sort((a, b) => a.distance - b.distance);
      if (
        !nearby.length ||
        nearby[0].distance + fix.accuracy > policy.radiusMeters ||
        excluded.has(nearby[0].target.id)
      ) {
        pending = null;
        return { status: 'watching' };
      }
      const target = nearby[0].target;
      // Colocated and repeated stops are also ambiguous: an entrance coordinate
      // does not establish which venue or occurrence the user reached.
      if (nearby[1] && nearby[1].distance - nearby[0].distance <= 2 * fix.accuracy) {
        pending = null;
        return { status: 'ambiguous' };
      }
      if (pending?.id !== target.id)
        pending = { id: target.id, first: fix.timestamp, samples: 0, accuracy: 0 };
      pending.samples += 1;
      pending.accuracy = Math.max(pending.accuracy, fix.accuracy);
      const dwellMs = fix.timestamp - pending.first;
      if (dwellMs < policy.dwellMs || pending.samples < policy.minSamples)
        return { status: 'dwelling', name: target.name };
      const arrival = {
        stopId: target.id,
        occurredAt: new Date(fix.timestamp).toISOString(),
        dwellSeconds: Math.floor(dwellMs / 1000),
        accuracyMeters: Math.ceil(pending.accuracy),
      };
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
