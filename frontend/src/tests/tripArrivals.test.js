import { describe, expect, it } from 'vitest';
import {
  ARRIVAL_POLICY,
  arrivalEvent,
  arrivalTargets,
  automaticArrivalExcludedStopIds,
  correctArrival,
  createArrivalDetector,
  distanceMeters,
  recordArrival,
} from '../services/tripArrivals';

const target = { id: 'park', name: 'Park', coordinates: [34, -118] };
const now = Date.parse('2026-11-07T12:00:00Z');
const fix = (seconds, extra = {}) => ({
  latitude: 34,
  longitude: -118,
  accuracy: 10,
  speed: 0,
  timestamp: now + seconds * 1000,
  ...extra,
});
const feed = (detector, seconds, extra, excluded) =>
  detector.sample(fix(seconds, extra), now + seconds * 1000, excluded);
const dwell = (detector, start = 0, extra = {}) =>
  [start, start + 20, start + 40, start + 60].map((s) => feed(detector, s, extra));

describe('arrival targets', () => {
  it('uses existing stable visit ids and resolves exact route identities without geometry guesses', () => {
    const trip = {
      route: { stops: [{ provider_id: 'park:1', coordinates: [34, -118] }] },
      itinerary: [
        {
          date: 'Day 1',
          stops: [
            { name: 'Park', provider_id: 'park:1' },
            { name: 'Departure' },
            { name: 'Missing', provider_id: 'missing' },
            { name: 'Meal', kind: 'meal', coordinates: [34, -118] },
            { name: 'Leaving', paired_departure: true, coordinates: [34, -118] },
          ],
        },
      ],
    };
    expect(arrivalTargets(trip)).toHaveLength(1);
    expect(arrivalTargets(trip)[0]).toMatchObject({ name: 'Park', coordinates: [34, -118] });
    expect(arrivalTargets(JSON.parse(JSON.stringify(trip)))).toEqual(arrivalTargets(trip));
  });
  it('allows precise direct coordinates and exact legacy arrival identity but rejects ambiguity', () => {
    const trip = {
      route: {
        stops: [
          { name: 'Legacy', type: 'hotel', address: '1 Main', coordinates: [35, -117] },
          { provider_id: 'duplicate', coordinates: [34, -118] },
          { provider_id: 'duplicate', coordinates: [35, -117] },
        ],
      },
      itinerary: [
        {
          stops: [
            { name: 'Direct', coordinates: [0, 0] },
            { name: 'Legacy', kind: 'arrival', type: 'hotel', address: '1 Main' },
            { name: 'Duplicate', provider_id: 'duplicate' },
            { name: 'Legacy' },
            { name: 'Malformed', coordinates: [-118, 34] },
          ],
        },
      ],
    };
    expect(arrivalTargets(trip).map((item) => item.name)).toEqual(['Direct', 'Legacy']);
    expect(arrivalTargets({ route: {}, itinerary: null })).toEqual([]);
  });
});

describe('conservative arrival detection', () => {
  it('requires a full minute of accurate samples and produces no raw coordinates', () => {
    const detector = createArrivalDetector([target]);
    const results = dwell(detector);
    expect(results.slice(0, 3).every((result) => result.status === 'dwelling')).toBe(true);
    expect(results[3]).toEqual({
      status: 'arrived',
      name: 'Park',
      arrival: {
        stopId: 'park',
        occurredAt: new Date(now + 60000).toISOString(),
        dwellSeconds: 60,
        accuracyMeters: 10,
      },
    });
    expect(feed(detector, 80, {}, new Set(['park'])).status).toBe('watching');
  });
  it.each([
    { accuracy: 36 },
    { accuracy: -1 },
    { latitude: 91 },
    { longitude: NaN },
    { timestamp: now - ARRIVAL_POLICY.maxAgeMs - 1 },
    { timestamp: now + 1 },
    { timestamp: NaN },
  ])('rejects bad, stale or future fixes and resets dwell: %j', (extra) => {
    const detector = createArrivalDetector([target]);
    feed(detector, 0);
    expect(detector.sample(fix(0, extra), now).status).toBe('waiting');
    expect(feed(detector, 20).status).toBe('dwelling');
    expect(feed(detector, 40).status).toBe('dwelling');
    expect(feed(detector, 60).arrival).toBeUndefined();
  });
  it('rejects duplicate/out-of-order fixes and starts fresh after interruptions', () => {
    const detector = createArrivalDetector([target]);
    feed(detector, 0);
    feed(detector, 20);
    expect(feed(detector, 20).status).toBe('waiting');
    expect(feed(detector, 15).status).toBe('waiting');
    expect(feed(detector, 40).status).toBe('dwelling');
    expect(feed(detector, 61).status).toBe('dwelling');
    expect(feed(detector, 81).arrival).toBeUndefined();
    detector.reset();
    expect(feed(detector, 100).arrival).toBeUndefined();
  });
  it('does not record drive-bys, leaving the radius, poor accuracy at the boundary or inferred movement', () => {
    const detector = createArrivalDetector([target]);
    expect(dwell(detector, 0, { speed: 10 }).every((result) => result.status === 'moving')).toBe(
      true
    );
    feed(detector, 80);
    expect(feed(detector, 100, { latitude: 34.001 }).status).toBe('moving');
    expect(feed(detector, 120, { latitude: 34.001 }).status).toBe('watching');
    expect(feed(detector, 140).status).toBe('moving');
    expect(feed(detector, 160).status).toBe('dwelling');
    expect(feed(detector, 180, { latitude: 34.0008, accuracy: 20 }).status).toBe('moving');
    expect(feed(detector, 200, { latitude: 34.0008, accuracy: 20 }).status).toBe('watching');
  });
  it('does not chain colocated repeat visits or choose between indistinguishable venues', () => {
    const repeat = createArrivalDetector([target, { ...target, id: 'repeat' }]);
    expect(dwell(repeat).every((result) => result.status === 'ambiguous')).toBe(true);
    expect(feed(repeat, 80, {}, new Set(['park'])).arrival).toBeUndefined();
    const sameEntrance = createArrivalDetector([target, { ...target, id: 'cafe', name: 'Cafe' }]);
    expect(dwell(sameEntrance).every((result) => result.status === 'ambiguous')).toBe(true);
    const ambiguous = createArrivalDetector([
      target,
      { id: 'next-door', coordinates: [34.00001, -118] },
    ]);
    expect(dwell(ambiguous).every((result) => result.status === 'ambiguous')).toBe(true);
  });
  it('rejects when the uncertainty circle can cross the midpoint between venues', () => {
    const meter = 1 / 111194.9266;
    const targets = [
      { id: 'first', coordinates: [0, 0] },
      { id: 'second', coordinates: [0, 60 * meter] },
    ];
    const detector = createArrivalDetector(targets);
    const result = feed(detector, 0, { latitude: 0, longitude: 15 * meter, accuracy: 20 });
    expect(result.status).toBe('ambiguous');
    // A competing stop must count even if its whole uncertainty circle is not
    // inside the arrival radius; it can still be the actual nearest venue.
    const edge = createArrivalDetector([targets[0], { id: 'edge', coordinates: [0, 150 * meter] }]);
    expect(feed(edge, 0, { latitude: 0, longitude: 60 * meter, accuracy: 35 }).status).toBe(
      'ambiguous'
    );
  });
  it('handles zero coordinates, unknown speed and great-circle distances', () => {
    expect(distanceMeters([0, 0], [0, 0])).toBe(0);
    expect(distanceMeters([0, 0], [0, 1])).toBeCloseTo(111194.9, 0);
    expect(dwell(createArrivalDetector([target]), 0, { speed: null })[3].arrival).toBeDefined();
  });
});

describe('arrival persistence contract', () => {
  it('is idempotent and preserves legacy fields while retaining only the event', () => {
    const event = arrivalEvent(42, {
      ...dwell(createArrivalDetector([target]))[3].arrival,
      latitude: 34,
    });
    expect(event).toMatchObject({
      schemaVersion: 1,
      type: 'trip.stop.arrived',
      source: 'web-foreground',
      tripId: 42,
    });
    expect(event).not.toHaveProperty('latitude');
    const original = { future: 'keep', visitedStopIds: ['other'] };
    const marked = recordArrival(original, event);
    expect(marked.future).toBe('keep');
    expect(marked.visitedStopIds).toEqual(['other', 'park']);
    expect(recordArrival(marked, event)).toBe(marked);
    expect(original.visitedStopIds).toEqual(['other']);
    const undone = correctArrival(marked, 42, 'park', now);
    expect(undone.arrivals).toEqual({});
    expect(automaticArrivalExcludedStopIds(undone)).toEqual(['park']);
    const restored = correctArrival(undone, 42, 'park', now);
    expect(restored.arrivals.park.source).toBe('manual');
    expect(restored.arrivals.park).not.toHaveProperty('accuracyMeters');
    expect(automaticArrivalExcludedStopIds(restored)).toEqual([]);
    expect(automaticArrivalExcludedStopIds({ automaticArrivalExcludedStopIds: 'bad' })).toEqual([]);
  });
});
