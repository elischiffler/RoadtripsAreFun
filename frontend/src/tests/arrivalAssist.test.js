import { describe, expect, it } from 'vitest';
import { createArrivalTracker, nextArrivalTarget } from '../services/arrivalAssist';
import { itineraryEntries } from '../services/tripPresentation';

const now = Date.parse('2030-05-04T12:00:00Z');
const target = {
  id: 'first',
  name: 'First stop',
  coordinates: [40, -105],
  earliest: now - 1,
  latest: now + 3600000,
};
const position = (time, changes = {}) => ({
  timestamp: time,
  coords: { latitude: 40, longitude: -105, accuracy: 10, speed: 0, ...changes },
});
const samples = (tracker, options = {}) =>
  [0, 15000, 30000, 45000].map((offset) =>
    tracker.observe(position(now + offset, options), target, now + offset)
  );

it('requires sustained, fresh, accurate near-stop readings and emits arrival only once', () => {
  const tracker = createArrivalTracker();
  expect(samples(tracker).map((result) => result.state)).toEqual([
    'waiting',
    'waiting',
    'waiting',
    'arrived',
  ]);
  expect(tracker.observe(position(now + 60000), target, now + 60000).state).toBe('waiting');
});

it.each([
  ['poor accuracy', { accuracy: 200 }],
  ['invalid accuracy', { accuracy: NaN }],
  ['invalid coordinates', { latitude: 91 }],
  ['moving', { speed: 10 }],
  ['invalid speed', { speed: -1 }],
  ['outside radius', { latitude: 40.002 }],
  ['accuracy circle extends outside radius', { latitude: 40.001, accuracy: 50 }],
])('does not mark a stop from %s', (_, changes) => {
  expect(
    samples(createArrivalTracker(), changes).every((result) => result.state === 'waiting')
  ).toBe(true);
});

it.each([0, 0.0006])(
  'requires departure and re-entry before another colocated/adjacent attraction (%s)',
  (offset) => {
    const tracker = createArrivalTracker();
    expect(samples(tracker).at(-1).state).toBe('arrived');
    const adjacent = { ...target, id: 'second', coordinates: [40 + offset, -105] };
    for (const elapsed of [60000, 75000, 90000, 105000]) {
      expect(tracker.observe(position(now + elapsed), adjacent, now + elapsed).reason).toBe(
        'departure'
      );
    }
    expect(
      tracker.observe(position(now + 120000, { latitude: 40.003 }), adjacent, now + 120000).state
    ).toBe('waiting');
    const second = [135000, 150000, 165000, 180000].map((elapsed) =>
      tracker.observe(position(now + elapsed, { latitude: 40 + offset }), adjacent, now + elapsed)
    );
    expect(second.map((result) => result.state)).toEqual([
      'waiting',
      'waiting',
      'waiting',
      'arrived',
    ]);
  }
);

it('cannot accumulate dwell from repeated, stale, future, sparse or jumped timestamps', () => {
  for (const acquired of [() => now, (time) => time - 16000, (time) => time + 3000]) {
    const tracker = createArrivalTracker();
    for (const offset of [0, 15000, 30000, 45000, 60000])
      expect(tracker.observe(position(acquired(now + offset)), target, now + offset).state).toBe(
        'waiting'
      );
  }
  const sparse = createArrivalTracker();
  for (const offset of [0, 20000, 40000, 60000])
    expect(sparse.observe(position(now + offset), target, now + offset).state).toBe('waiting');
  const jump = createArrivalTracker();
  for (const offset of [0, 15000, 30000, 45000])
    expect(jump.observe(position(now + offset), target, now).state).toBe('waiting');
});

it('resets dwell after drift, an invalid reading or a pending save', () => {
  const tracker = createArrivalTracker();
  tracker.observe(position(now), target, now);
  tracker.observe(position(now + 15000), target, now + 15000);
  tracker.observe(position(now + 30000, { accuracy: 500 }), target, now + 30000);
  expect(tracker.observe(position(now + 45000), target, now + 45000).state).toBe('waiting');
  tracker.reset();
  expect(tracker.observe(position(now + 60000), target, now + 60000).state).toBe('waiting');
  const drift = createArrivalTracker();
  drift.observe(position(now), target, now);
  drift.observe(position(now + 15000, { latitude: 40.0006 }), target, now + 15000);
  expect(drift.observe(position(now + 30000), target, now + 30000).state).toBe('waiting');
});

it('does not complete a trip from another planned day or mark a new target using previous dwell', () => {
  const tracker = createArrivalTracker();
  expect(tracker.observe(position(now), { ...target, earliest: now + 86400000 }, now).reason).toBe(
    'schedule'
  );
  for (const offset of [0, 15000, 30000])
    tracker.observe(position(now + offset), target, now + offset);
  expect(tracker.observe(position(now + 45000), { ...target, id: 'next' }, now + 45000).state).toBe(
    'waiting'
  );
  expect(
    tracker.observe(position(now + 60000), { ...target, latest: now }, now + 60000).reason
  ).toBe('schedule');
});

const stop = {
  provider_id: 'place:a',
  name: 'Attraction',
  type: 'stop',
  kind: 'arrival',
  arrival_time: '2030-05-04T12:00:00Z',
  departure_time: '2030-05-04T12:45:00Z',
  coordinates: [40, -105],
};
const trip = () => ({
  route: { departure_time: '2030-05-04T11:00:00Z', stops: [stop] },
  itinerary: [
    {
      date: 'Today',
      stops: [
        { kind: 'meal', name: 'Lunch' },
        { ...stop, coordinates: undefined },
      ],
    },
  ],
  presentation: {},
});

describe('authoritative next attraction', () => {
  it('matches the next unvisited attraction to unique route timing and coordinates', () => {
    const data = trip();
    expect(nextArrivalTarget(data)).toMatchObject({ name: 'Attraction', coordinates: [40, -105] });
    data.presentation.visitedStopIds = [itineraryEntries(data.itinerary)[0].stops[0].id];
    expect(nextArrivalTarget(data)).toBeNull();
  });
  it.each(['hotel', 'end'])('excludes %s, meals and optional suggestions', (type) => {
    const data = trip();
    data.itinerary[0].stops[1].type = type;
    expect(nextArrivalTarget(data)).toBeNull();
    data.itinerary[0].stops[1] = { ...stop, optional: true };
    expect(nextArrivalTarget(data)).toBeNull();
  });
  it('rejects ambiguous, unmatched, invalid-coordinate and undated saved routes', () => {
    const data = trip();
    data.route.stops = [stop, stop];
    expect(nextArrivalTarget(data)).toBeNull();
    data.route.stops = [{ ...stop, arrival_time: 'different' }];
    expect(nextArrivalTarget(data)).toBeNull();
    data.route.stops = [{ ...stop, coordinates: [Infinity, -105] }];
    expect(nextArrivalTarget(data)).toBeNull();
    data.route.stops = [stop];
    data.route.departure_time = '2030-05-04T11:00:00';
    expect(nextArrivalTarget(data)).toBeNull();
  });
});
