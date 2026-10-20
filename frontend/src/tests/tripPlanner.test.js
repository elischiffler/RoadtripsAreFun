import { beforeEach, expect, it, vi } from 'vitest';
import axios from '../services/protectedRequest';
import { getFreshRoutingAlgorithm } from '../services/routingSettings';
import { fixtureSession } from './sessionFixtures';
import { newSetupDraft, preferenceWeights } from '../pages/TripSetup/setupModel';
import {
  resolveTripLocation,
  planStructuredRoute,
  planStructuredItinerary,
  structuredTripInputs,
  plannerError,
} from '../services/tripPlanner';

vi.mock('../services/protectedRequest', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../services/routingSettings', () => ({ getFreshRoutingAlgorithm: vi.fn() }));
const address = { address: 'Boulder, Colorado', latitude: 40, longitude: -105 };
const destination = { address: 'Denver, Colorado', latitude: 39.7, longitude: -104.9 };
beforeEach(() => {
  vi.resetAllMocks();
  fixtureSession();
  getFreshRoutingAlgorithm.mockResolvedValue(null);
  import.meta.env.VITE_BACKEND_SERVER = 'http://fixture/';
});
it('accepts single provider matches and explicit multiple-choice 409 results', async () => {
  const signal = new AbortController().signal;
  axios.post.mockResolvedValueOnce({ data: address });
  expect(await resolveTripLocation('Boulder', signal)).toEqual([address]);
  expect(axios.post.mock.calls[0][2].signal).toBe(signal);
  axios.post.mockRejectedValueOnce({
    response: { status: 409, data: { detail: { candidates: [address, destination] } } },
  });
  expect(await resolveTripLocation('ambiguous', signal)).toEqual([address, destination]);
  axios.post.mockRejectedValueOnce({ response: { status: 404 } });
  await expect(resolveTripLocation('missing', signal)).rejects.toMatchObject({
    response: { status: 404 },
  });
  axios.post.mockResolvedValueOnce({ data: { ...address, latitude: NaN } });
  await expect(resolveTripLocation('bad', signal)).rejects.toThrow(/usable/);
});
it('submits the actual complete preference vector, occupancy and local departure directly to planning', async () => {
  const draft = {
    ...newSetupDraft(),
    date: '2027-06-01',
    interests: ['food'],
    travelers: '2',
    rooms: [{ adults: '1', children: '8' }],
  };
  const initial = {
    geometry: {
      coordinates: [
        [-105, 40],
        [-104.9, 39.7],
      ],
    },
  };
  const route = {
    coordinates: [
      [40, -105],
      [39.7, -104.9],
    ],
    geometry: initial.geometry,
    distance: 50000,
    duration: 3600,
    stops: [{ visit_duration_seconds: 2700, leaving_time: '2027-06-01T10:00:00-06:00' }],
  };
  axios.get.mockResolvedValueOnce({ data: initial });
  axios.post.mockResolvedValueOnce({ data: route });
  const signal = new AbortController().signal;
  expect(await planStructuredRoute(draft, address, destination, signal)).toEqual(route);
  const [url, payload, config] = axios.post.mock.calls[0];
  expect(url).toBe('http://fixture/generate-final-route');
  expect(payload).toEqual({ initial_route: initial, ...structuredTripInputs(draft) });
  expect(payload.persona_weights).toEqual(preferenceWeights(draft));
  expect(Object.keys(payload.persona_weights)).toHaveLength(14);
  expect(payload.start).toBe('2027-06-01T09:00:00');
  expect(payload.hotel_rooms).toEqual([{ adults: 1, child_ages: [8] }]);
  expect(config.signal).toBe(signal);
  expect(payload).not.toHaveProperty('message');
  axios.post.mockResolvedValueOnce({ data: [{ date: 'Tuesday', stops: route.stops }] });
  await planStructuredItinerary(route, signal);
  expect(axios.post.mock.calls[1][1]).toEqual({ route });
});
it('rejects incomplete results and preserves backend validation messages', async () => {
  axios.get.mockResolvedValue({ data: {} });
  axios.post.mockResolvedValueOnce({ data: {} });
  await expect(
    planStructuredRoute(newSetupDraft(), address, destination, new AbortController().signal)
  ).rejects.toThrow(/complete route/);
  axios.post.mockResolvedValueOnce({ data: [] });
  await expect(planStructuredItinerary({}, new AbortController().signal)).rejects.toThrow(
    /itinerary/
  );
  expect(plannerError({ response: { data: { detail: 'Unsupported occupancy' } } })).toBe(
    'Unsupported occupancy'
  );
  expect(plannerError({ response: { data: { detail: [{ msg: 'Invalid date' }] } } })).toBe(
    'Invalid date'
  );
});
