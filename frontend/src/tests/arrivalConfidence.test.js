// Guard cases migrated from the original ArrivalAssist implementation.
import { expect, it } from 'vitest';
import { createArrivalDetector, nextArrivalTarget } from '../services/tripArrivals';
import { itineraryEntries } from '../services/tripPresentation';
const now = Date.parse('2030-05-04T12:00:00Z');
const target = {
  id: 'first',
  name: 'First stop',
  coordinates: [40, -105],
  earliest: now - 1,
  latest: now + 3600000,
};
const fix = (offset, changes = {}) => ({
  latitude: 40,
  longitude: -105,
  accuracy: 10,
  speed: 0,
  timestamp: now + offset,
  ...changes,
});
const samples = (detector, changes = {}) =>
  [0, 15000, 30000, 45000, 60000].map((offset) =>
    detector.sample(fix(offset, changes), now + offset)
  );
it('requires receipt and acquisition dwell, strictly fresh samples and emits only once', () => {
  const detector = createArrivalDetector([target]);
  expect(samples(detector).map((result) => result.status)).toEqual([
    'dwelling',
    'dwelling',
    'dwelling',
    'dwelling',
    'arrived',
  ]);
  expect(detector.sample(fix(75000), now + 75000).arrival).toBeUndefined();
  const jumped = createArrivalDetector([target]);
  for (const offset of [0, 15000, 30000, 45000, 60000])
    expect(jumped.sample(fix(offset), now).arrival).toBeUndefined();
});
it.each([
  ['poor accuracy', { accuracy: 200 }],
  ['invalid accuracy', { accuracy: NaN }],
  ['invalid coordinate', { latitude: 91 }],
  ['moving', { speed: 10 }],
  ['invalid speed', { speed: -1 }],
  ['outside radius', { latitude: 40.002 }],
  ['uncertain boundary', { latitude: 40.0007, accuracy: 35 }],
])('does not record %s fixes', (_, change) =>
  expect(samples(createArrivalDetector([target]), change).every((result) => !result.arrival)).toBe(
    true
  )
);
it('resets on repeated, out-of-order, stale, future, sparse and inaccurate readings', () => {
  for (const stamp of [() => now, (offset) => now + offset - 10001, (offset) => now + offset + 1]) {
    const detector = createArrivalDetector([target]);
    for (const offset of [0, 15000, 30000, 45000, 60000])
      expect(
        detector.sample(fix(offset, { timestamp: stamp(offset) }), now + offset).arrival
      ).toBeUndefined();
  }
  const sparse = createArrivalDetector([target]);
  for (const offset of [0, 16000, 32000, 48000, 64000])
    expect(sparse.sample(fix(offset), now + offset).arrival).toBeUndefined();
  const reset = createArrivalDetector([target]);
  reset.sample(fix(0), now);
  reset.sample(fix(15000), now + 15000);
  reset.sample(fix(30000, { accuracy: 500 }), now + 30000);
  expect(reset.sample(fix(45000), now + 45000).arrival).toBeUndefined();
  reset.reset();
  expect(reset.sample(fix(60000), now + 60000).arrival).toBeUndefined();
});
it('does not infer current visits on another planned day', () => {
  expect(
    createArrivalDetector([{ ...target, earliest: now + 86400000, latest: now + 90000000 }]).sample(
      fix(0),
      now
    ).status
  ).toBe('schedule');
  expect(createArrivalDetector([{ ...target, latest: now - 1 }]).sample(fix(0), now).status).toBe(
    'schedule'
  );
});
it('requires departure and a new dwell for an adjacent next target, retaining latch across reset', () => {
  const second = { ...target, id: 'second', coordinates: [40.00054, -105] };
  const detector = createArrivalDetector([target, second]);
  expect(samples(detector).at(-1).status).toBe('arrived');
  detector.reset();
  for (const offset of [75000, 90000, 105000, 120000])
    expect(detector.sample(fix(offset), now + offset).status).toBe('departure');
  detector.sample(fix(135000, { latitude: 40.003 }), now + 135000);
  detector.sample(fix(150000, { latitude: 40.003 }), now + 150000);
  detector.sample(fix(165000, { latitude: 40.00054 }), now + 165000);
  const results = [180000, 195000, 210000, 225000, 240000].map((offset) =>
    detector.sample(fix(offset, { latitude: 40.00054 }), now + offset)
  );
  expect(results.at(-1).status).toBe('arrived');
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
it('matches only the next unique timed route attraction and honors manual suppression', () => {
  const data = trip();
  expect(nextArrivalTarget(data)).toMatchObject({ name: 'Attraction', coordinates: [40, -105] });
  const id = itineraryEntries(data.itinerary)[0].stops[0].id;
  data.presentation.visitedStopIds = [id];
  expect(nextArrivalTarget(data)).toBeNull();
  data.presentation = { automaticArrivalExcludedStopIds: [id] };
  expect(nextArrivalTarget(data)).toBeNull();
});
it.each(['hotel', 'end'])('excludes %s, meals and optional suggestions', (type) => {
  const data = trip();
  data.itinerary[0].stops[1].type = type;
  expect(nextArrivalTarget(data)).toBeNull();
  data.itinerary[0].stops[1] = { ...stop, optional: true };
  expect(nextArrivalTarget(data)).toBeNull();
});
it('rejects duplicate, unmatched, malformed-coordinate and naive departure records', () => {
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

it('resets sustained slow drift at the anchor boundary, then requires a new full dwell', () => {
  const detector = createArrivalDetector([target]);
  detector.sample(fix(0), now);
  detector.sample(fix(15000, { latitude: 40.0002 }), now + 15000);
  detector.sample(fix(30000, { latitude: 40.0004 }), now + 30000);
  detector.sample(fix(45000, { latitude: 40.0006 }), now + 45000);
  expect(detector.sample(fix(60000, { latitude: 40.0006 }), now + 60000).arrival).toBeUndefined();
  for (const offset of [75000, 90000])
    expect(
      detector.sample(fix(offset, { latitude: 40.0006 }), now + offset).arrival
    ).toBeUndefined();
  expect(detector.sample(fix(105000, { latitude: 40.0006 }), now + 105000).status).toBe('arrived');
});
it('refuses malformed or undated direct detector targets', () => {
  for (const bad of [
    { ...target, coordinates: [NaN, 0] },
    { ...target, earliest: undefined },
    { ...target, latest: now - 2 },
  ])
    expect(createArrivalDetector([bad]).sample(fix(0), now).status).toBe('unavailable');
});
