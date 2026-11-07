import { beforeEach, expect, it, vi } from 'vitest';
import request from '../services/protectedRequest';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
import { newSetupDraft, preferenceWeights } from '../pages/TripSetup/setupModel';
import {
  assessPlanningCandidate,
  buildCandidatePayload,
  cancelCandidateRequest,
  candidateDraftKey,
  candidateTripInputs,
  confirmPlanningCandidate,
  registerCandidateRequest,
  validateCandidate,
} from '../services/planningCandidates';
import { candidateErrorMessage, safeCandidateError } from '../services/planningCandidateErrors';
import { streamPlanningCandidate } from '../services/tripRouteStream';
import { getFreshRoutingAlgorithm } from '../services/routingSettings';
vi.mock('../services/protectedRequest', () => ({ default: { post: vi.fn(), delete: vi.fn() } }));
vi.mock('../services/tripRouteStream', () => ({ streamPlanningCandidate: vi.fn() }));
vi.mock('../services/routingSettings', () => ({ getFreshRoutingAlgorithm: vi.fn() }));
const draft = { ...newSetupDraft(), start: 'A', destination: 'B', date: '2027-06-01' };
const route = {
  distance: 10,
  duration: 3600,
  coordinates: [
    [40, -105],
    [41, -104],
  ],
  geometry: {
    type: 'LineString',
    coordinates: [
      [-105, 40],
      [-104, 41],
    ],
  },
  reserve_meal_slots: true,
  trip_mode: 'one_day',
  one_day_proof: { status: 'validated', threshold_seconds: 43200, elapsed_seconds: 7200 },
};
const candidate = {
  candidate_id: 'abcdefghijklmnop',
  input_key: 'a'.repeat(64),
  expires_at: '2099-01-01T00:00:00Z',
  one_day: { eligible: true, elapsed_seconds: 7200, threshold_seconds: 43200 },
  candidate_route: route,
};
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  fixtureSession();
  import.meta.env.VITE_BACKEND_SERVER = 'http://fixture/';
  getFreshRoutingAlgorithm.mockResolvedValue(null);
});
it('keeps semantic weights exact and removes lodging from the assessment key and payload', () => {
  const inputs = candidateTripInputs(draft);
  expect(inputs.persona_weights).toEqual(preferenceWeights(draft));
  expect(inputs).not.toHaveProperty('hotel_rooms');
  expect(inputs).not.toHaveProperty('budget');
  expect(Object.keys(inputs.scheduling_policy)).toEqual(['daily_schedule']);
  expect(
    candidateDraftKey({ ...draft, rooms: [{ adults: '5', children: '' }], budget: '999' })
  ).toBe(candidateDraftKey(draft));
  expect(candidateDraftKey({ ...draft, travelers: '2' })).not.toBe(candidateDraftKey(draft));
});
it('registers without planning and preserves a frozen algorithm and payload for explicit uncertain retries', async () => {
  request.post.mockResolvedValue({
    data: { request_id: 'same-id', expires_at: candidate.expires_at },
  });
  await registerCandidateRequest('same-id');
  expect(streamPlanningCandidate).not.toHaveBeenCalled();
  const payload = await buildCandidatePayload(draft, route, 'same-id');
  getFreshRoutingAlgorithm.mockResolvedValue('changed');
  streamPlanningCandidate.mockResolvedValue(candidate);
  await assessPlanningCandidate(draft, route, 'same-id', undefined, undefined, payload);
  await assessPlanningCandidate(draft, route, 'same-id', undefined, undefined, payload);
  expect(streamPlanningCandidate.mock.calls[0][0]).toBe(payload);
  expect(streamPlanningCandidate.mock.calls[1][0]).toBe(payload);
  expect(getFreshRoutingAlgorithm).toHaveBeenCalledTimes(1);
  expect(request.post).toHaveBeenCalledTimes(1);
});
it('requires complete actual elapsed proof below12h, never a short road duration alone', () => {
  expect(validateCandidate(candidate)).toBe(candidate);
  for (const broken of [
    { ...candidate, candidate_route: null },
    { ...candidate, one_day: { ...candidate.one_day, elapsed_seconds: 43200 } },
    { ...candidate, one_day: { ...candidate.one_day, elapsed_seconds: null } },
    { ...candidate, candidate_route: { ...route, coordinates: [null, null] } },
  ])
    expect(() => validateCandidate(broken)).toThrow();
  expect(
    validateCandidate({
      ...candidate,
      one_day: { ...candidate.one_day, eligible: false, elapsed_seconds: null },
      candidate_route: null,
    }).one_day.eligible
  ).toBe(false);
});
it('sends room occupancy only after an explicit flexible-stay choice and accepts zero actual hotels', async () => {
  request.post.mockResolvedValue({ data: route });
  await confirmPlanningCandidate(candidate, 'one_day', draft);
  expect(request.post.mock.calls[0][1]).toEqual({
    input_key: candidate.input_key,
    trip_mode: 'one_day',
    traveler_count: 1,
  });
  request.post.mockResolvedValue({ data: { ...route, trip_mode: 'overnight', stops: [] } });
  await confirmPlanningCandidate(candidate, 'overnight', draft);
  expect(request.post.mock.calls[1][1]).toMatchObject({
    trip_mode: 'overnight',
    budget: 150,
    hotel_rooms: [{ adults: 1, child_ages: [] }],
  });
});
it('uses local fixed copy only for exact status/code and never replays expired or unknown requests', async () => {
  const expected = candidateErrorMessage(410, 'candidate_expired');
  request.post.mockRejectedValue({
    response: { status: 410, data: { code: 'candidate_expired', detail: 'provider secret' } },
  });
  await expect(confirmPlanningCandidate(candidate, 'one_day', draft)).rejects.toMatchObject({
    message: expected,
  });
  expect(request.post).toHaveBeenCalledTimes(1);
  for (const status of [401, 500, undefined])
    expect(candidateErrorMessage(status, 'candidate_expired')).toBeUndefined();
  expect(candidateErrorMessage(422, '__proto__')).toBeUndefined();
  request.post.mockRejectedValue({
    response: { status: 500, data: { code: 'candidate_expired', detail: 'provider secret' } },
  });
  await expect(registerCandidateRequest('id')).rejects.not.toHaveProperty(
    'message',
    'provider secret'
  );
});
it('does not dispatch cancellation as a different account or accept late assessment results', async () => {
  const { getSession } = await import('../services/session');
  const session = getSession();
  signOut();
  await cancelCandidateRequest('old-id', session);
  expect(request.delete).not.toHaveBeenCalled();
  fixtureSession('new');
  let finish;
  streamPlanningCandidate.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const pending = assessPlanningCandidate(draft, route, 'id', undefined, undefined, {});
  signOut();
  finish(candidate);
  await expect(pending).rejects.toMatchObject({ code: 'session-changed' });
});

it('keeps actual timing conflicts actionable while retiring the old clock-band restriction', () => {
  expect(candidateErrorMessage(422, 'rhythm_availability_conflict')).toMatch(
    /road leg falls outside driving availability/
  );
  expect(candidateErrorMessage(422, 'unsupported_overnight_rhythm')).toBeUndefined();
  const error = safeCandidateError({
    response: {
      status: 422,
      data: { code: 'unsupported_overnight_rhythm', detail: 'Night driving must be one day only' },
    },
  });
  expect(error.message).not.toMatch(/one day only/);
});

it('only exposes fixed actionable lodging guidance for the exact422 contract', () => {
  const message =
    'The dated hotel quote does not cover the planned rest interval. Choose a later departure or adjust the daily rhythm and check options again. Confirm hotel check-in and checkout times before booking.';
  expect(candidateErrorMessage(422, 'lodging_stay_conflict')).toBe(message);
  expect(candidateErrorMessage(500, 'lodging_stay_conflict')).toBeUndefined();
  const error = safeCandidateError({
    response: {
      status: 422,
      data: { code: 'lodging_stay_conflict', detail: 'Private hotel provider diagnostics' },
    },
  });
  expect(error.message).toBe(message);
  expect(error.message).not.toMatch(/Private hotel/);
});
