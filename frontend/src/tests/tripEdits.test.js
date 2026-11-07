import { beforeEach, expect, it, vi } from 'vitest';
import request from '../services/protectedRequest';
import { initializeUserData } from '../services/savedTrips';
import { isCurrentSession } from '../services/session';
import {
  editedTripSnapshot,
  pendingTripEdit,
  persistTripEdit,
  previewTripEdit,
  reconcileTripEdit,
} from '../services/tripEdits';
vi.mock('../services/protectedRequest', () => ({ default: { post: vi.fn(), put: vi.fn() } }));
vi.mock('../services/savedTrips', () => ({ initializeUserData: vi.fn() }));
vi.mock('../services/session', () => ({
  getSession: () => ({ accessToken: 'fixture' }),
  isCurrentSession: vi.fn(() => true),
}));
const original = () => ({
  chatId: 1,
  savedRevision: 'a'.repeat(64),
  agentChatId: 'guid',
  stops: 1,
  tripProfile: { num_stops: 1, traveler_count: 2 },
  presentation: { visitedStopIds: ['old'], custom: 'kept' },
  route: {
    stops: [
      { name: 'Old', type: 'stop' },
      { name: 'End', type: 'end' },
    ],
  },
  itinerary: [{ date: 'fixture', stops: [{ kind: 'meal' }] }],
});
const preview = {
  route: {
    stops: [
      { name: 'Old', type: 'stop' },
      { name: 'New', type: 'stop' },
      { name: 'End', type: 'end' },
    ],
  },
  itinerary: [],
};
const loaded = (trip) => ({
  UserData: { chatlogs: { getChatDataById: () => trip } },
  chats: [{ id: 1, messages: [{ type: 'loading-chat' }, { text: 'kept' }] }],
});
beforeEach(() => {
  vi.clearAllMocks();
  isCurrentSession.mockReturnValue(true);
  vi.stubEnv('VITE_BACKEND_SERVER', 'http://fixture/');
});
it('previews authenticated edits with meal slots and no saved write', async () => {
  request.post.mockResolvedValue({ data: preview });
  const signal = new AbortController().signal;
  expect(await previewTripEdit(original(), { provider_id: 'catalog:1' }, 'add', 1, signal)).toEqual(
    preview
  );
  expect(request.post).toHaveBeenCalledWith(
    'http://fixture/route-edit',
    expect.objectContaining({
      provider_id: 'catalog:1',
      action: 'add',
      stop_index: 1,
      include_meal_slots: true,
    }),
    { signal }
  );
  expect(request.put).not.toHaveBeenCalled();
});
it('preserves metadata, clears obsolete visits, and updates counts only after additions', () => {
  const trip = original();
  trip.presentation.arrivals = { old: { source: 'web-foreground' } };
  trip.presentation.automaticArrivalExcludedStopIds = ['old'];
  const next = editedTripSnapshot(trip, preview);
  expect(next.presentation).toEqual({ visitedStopIds: [], custom: 'kept' });
  expect(next).toMatchObject({
    stops: 2,
    tripProfile: { num_stops: 2, traveler_count: 2 },
    presentation: { visitedStopIds: [], custom: 'kept' },
    agentChatId: 'guid',
  });
  expect(trip.presentation.visitedStopIds).toEqual(['old']);
  expect(editedTripSnapshot(trip, { route: trip.route, itinerary: [] }).tripProfile).toBe(
    trip.tripProfile
  );
});
it('preflights current saved state then writes exactly once without create fallback', async () => {
  const trip = original();
  const logs = {};
  const next = editedTripSnapshot(trip, preview);
  initializeUserData.mockResolvedValue(loaded(trip));
  request.put.mockResolvedValue({ data: { savedRevision: 'a'.repeat(64) } });
  expect(await persistTripEdit(trip, next, [], logs)).toEqual({ status: 'saved', snapshot: next });
  expect(request.put).toHaveBeenCalledWith(
    'http://fixture/chats/update/1',
    expect.objectContaining({
      ExpectedRevision: 'a'.repeat(64),
      ChatData: next,
      ChatLog: { id: 1, messages: [{ text: 'kept' }] },
    })
  );
  expect(request.post).not.toHaveBeenCalled();
  expect(pendingTripEdit(logs, 1)).toBeUndefined();
});
it('recognizes a committed snapshot after an unsuccessful response', async () => {
  const trip = original();
  const logs = {};
  const next = editedTripSnapshot(trip, preview);
  initializeUserData.mockResolvedValueOnce(loaded(trip)).mockResolvedValueOnce(loaded(next));
  request.put.mockRejectedValue(new Error('lost response'));
  expect(await persistTripEdit(trip, next, [], logs)).toEqual({ status: 'saved', snapshot: next });
  expect(request.put).toHaveBeenCalledTimes(1);
});
it('blocks retry even when immediate readback is still original after network failure', async () => {
  const trip = original();
  const logs = {};
  const next = editedTripSnapshot(trip, preview);
  initializeUserData.mockResolvedValue(loaded(trip));
  request.put.mockRejectedValue(new Error('network'));
  expect(await persistTripEdit(trip, next, [], logs)).toEqual({ status: 'uncertain' });
  expect(await persistTripEdit(trip, next, [], logs)).toEqual({ status: 'uncertain' });
  expect(request.put).toHaveBeenCalledTimes(1);
  initializeUserData.mockResolvedValue(loaded(next));
  expect(await reconcileTripEdit(logs, 1)).toEqual({ status: 'saved', snapshot: next });
});
it('blocks stale, missing, and unavailable saved snapshots before any write', async () => {
  const trip = original();
  const next = editedTripSnapshot(trip, preview);
  initializeUserData.mockResolvedValueOnce(loaded({ ...trip, route: { stops: [] } }));
  expect(await persistTripEdit(trip, next, [], {})).toEqual({ status: 'conflict' });
  initializeUserData.mockResolvedValueOnce(loaded(null));
  expect(await persistTripEdit(trip, next, [], {})).toEqual({ status: 'conflict' });
  initializeUserData.mockResolvedValueOnce(null);
  expect(await persistTripEdit(trip, next, [], {})).toEqual({ status: 'unavailable' });
  expect(request.put).not.toHaveBeenCalled();
});
it('does not save after account switches during preflight', async () => {
  const trip = original();
  initializeUserData.mockImplementation(async () => {
    isCurrentSession.mockReturnValue(false);
    return loaded(trip);
  });
  expect(await persistTripEdit(trip, editedTripSnapshot(trip, preview), [], {})).toEqual({
    status: 'stale',
  });
  expect(request.put).not.toHaveBeenCalled();
});

it('prevents two preflights from dispatching concurrent writes', async () => {
  const trip = original();
  const logs = {};
  const next = editedTripSnapshot(trip, preview);
  initializeUserData.mockResolvedValue(loaded(trip));
  let finish;
  request.put.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const first = persistTripEdit(trip, next, [], logs);
  const second = persistTripEdit(trip, next, [], logs);
  expect(await second).toEqual({ status: 'uncertain' });
  expect(request.put).toHaveBeenCalledTimes(1);
  finish({ data: { savedRevision: 'a'.repeat(64) } });
  expect(await first).toEqual({ status: 'saved', snapshot: next });
});

it.each([404, 409])(
  'treats atomic save rejection %s as conflict without retry or uncertain state',
  async (status) => {
    const trip = original();
    const logs = {};
    initializeUserData.mockResolvedValue(loaded(trip));
    request.put.mockRejectedValue({ response: { status } });
    expect(await persistTripEdit(trip, editedTripSnapshot(trip, preview), [], logs)).toEqual({
      status: 'conflict',
    });
    expect(pendingTripEdit(logs, 1)).toBeUndefined();
    expect(request.put).toHaveBeenCalledTimes(1);
    expect(initializeUserData).toHaveBeenCalledTimes(1);
  }
);
it('rejects a changed server revision even when displayed route fields match', async () => {
  const trip = original();
  initializeUserData.mockResolvedValue(loaded({ ...trip, savedRevision: 'b'.repeat(64) }));
  expect(await persistTripEdit(trip, editedTripSnapshot(trip, preview), [], {})).toEqual({
    status: 'conflict',
  });
  expect(request.put).not.toHaveBeenCalled();
});
