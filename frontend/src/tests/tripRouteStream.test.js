import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { streamTripRoute } from '../services/tripRouteStream';
import { fixtureSession, fixtureToken } from './sessionFixtures';
import { cognitoClient } from '../services/cognito';
import { getSession, signOut } from '../services/session';
vi.mock('../services/cognito', () => ({ cognitoClient: { send: vi.fn() } }));
const route = {
  coordinates: [
    [40, -105],
    [39.7, -104.9],
  ],
  duration: 3600,
  distance: 50000,
};
const encoder = new TextEncoder();
function streamed(events, { chunks, tail = '' } = {}) {
  const data = events.map((event) => JSON.stringify(event) + '\n').join('') + tail;
  const pieces = chunks ? [data.slice(0, chunks), data.slice(chunks)] : [data];
  return {
    ok: true,
    headers: new Headers({ 'content-type': 'application/x-ndjson' }),
    body: new ReadableStream({
      start(controller) {
        for (const text of pieces) controller.enqueue(encoder.encode(text));
        controller.close();
      },
    }),
  };
}
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  fixtureSession('user', undefined, 'refresh');
  import.meta.env.VITE_BACKEND_SERVER = 'https://api.example.test/';
  vi.stubGlobal('fetch', vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  signOut();
});
it('uses account auth and consumes split actual stage events and the final route', async () => {
  const progress = vi.fn();
  fetch.mockResolvedValue(
    streamed(
      [
        { type: 'progress', stage: 'route.solver', state: 'completed' },
        { type: 'heartbeat' },
        { type: 'result', response: route },
      ],
      { chunks: 8 }
    )
  );
  expect(await streamTripRoute({ budget: 150 }, new AbortController().signal, progress)).toEqual(
    route
  );
  expect(fetch.mock.calls[0][0]).toBe('https://api.example.test/generate-final-route/stream');
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer ' + getSession().accessToken);
  expect(fetch.mock.calls[0][1].headers['X-Studio-Session']).toBeUndefined();
  expect(progress).toHaveBeenCalledTimes(2);
});
it('renews once only for an exact pre-stream verifier rejection', async () => {
  const old = getSession().accessToken;
  fetch
    .mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid authentication token' }),
    })
    .mockResolvedValueOnce(streamed([{ type: 'result', response: route }]));
  cognitoClient.send.mockResolvedValue({
    AuthenticationResult: {
      AccessToken: fixtureToken('user', Date.now() / 1000 + 7200),
      IdToken: fixtureToken('user', Date.now() / 1000 + 7200, 'id'),
      RefreshToken: 'new',
    },
  });
  await expect(streamTripRoute({}, new AbortController().signal, vi.fn())).resolves.toEqual(route);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(cognitoClient.send).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[1][1].headers.Authorization).not.toBe('Bearer ' + old);
});
it('does not replay arbitrary HTTP401 or any error after streaming has started', async () => {
  fetch.mockResolvedValueOnce({
    ok: false,
    status: 401,
    json: async () => ({ detail: 'Provider rejected request' }),
  });
  await expect(streamTripRoute({}, new AbortController().signal)).rejects.toMatchObject({
    response: { status: 401 },
  });
  expect(fetch).toHaveBeenCalledOnce();
  expect(cognitoClient.send).not.toHaveBeenCalled();
  fetch.mockReset().mockResolvedValueOnce(
    streamed([
      { type: 'progress', stage: 'route.gathering', state: 'started' },
      { type: 'error', status: 401 },
    ])
  );
  await expect(streamTripRoute({}, new AbortController().signal)).rejects.toMatchObject({
    response: { status: 401 },
  });
  expect(fetch).toHaveBeenCalledOnce();
  expect(cognitoClient.send).not.toHaveBeenCalled();
});
it('does not return a late route if the owner changes while consuming a chunk', async () => {
  fetch.mockResolvedValue(
    streamed([
      { type: 'progress', stage: 'route.validation', state: 'completed' },
      { type: 'result', response: route },
    ])
  );
  await expect(
    streamTripRoute({}, new AbortController().signal, () => signOut())
  ).rejects.toMatchObject({ code: 'session-changed' });
  expect(fetch).toHaveBeenCalledOnce();
});
it('preserves a dedicated meal conflict explanation without exposing arbitrary provider details or replaying', async () => {
  const detail = 'Lunch cannot fit before your driving cutoff. Edit your schedule.';
  fetch.mockResolvedValueOnce(
    streamed([{ type: 'error', status: 422, code: 'meal_schedule_conflict', detail }])
  );
  await expect(streamTripRoute({}, new AbortController().signal)).rejects.toMatchObject({
    response: { status: 422, data: { detail } },
  });
  expect(fetch).toHaveBeenCalledOnce();
  expect(cognitoClient.send).not.toHaveBeenCalled();

  fetch
    .mockReset()
    .mockResolvedValueOnce(
      streamed([{ type: 'error', status: 503, detail: 'Private provider diagnostics' }])
    );
  await expect(streamTripRoute({}, new AbortController().signal)).rejects.toMatchObject({
    response: { status: 503, data: undefined },
  });
  expect(fetch).toHaveBeenCalledOnce();
});
it.each([
  [() => streamed([{ type: 'heartbeat' }]), /without a result/],
  [
    () => ({ ok: true, headers: new Headers({ 'content-type': 'text/html' }), body: {} }),
    /Unexpected trip progress response/,
  ],
  [() => streamed([], { tail: 'not-json' }), /JSON/],
  [() => streamed([{ type: 'unknown' }]), /Unexpected trip progress event/],
])('rejects incomplete or malformed streams without replay', async (make, pattern) => {
  fetch.mockResolvedValue(make());
  await expect(streamTripRoute({}, new AbortController().signal)).rejects.toThrow(pattern);
  expect(fetch).toHaveBeenCalledOnce();
});
it('does not dispatch an already aborted request or let a presentation exception lose a result', async () => {
  const controller = new AbortController();
  controller.abort();
  await expect(streamTripRoute({}, controller.signal)).rejects.toMatchObject({
    name: 'AbortError',
  });
  expect(fetch).not.toHaveBeenCalled();
  fetch.mockResolvedValue(
    streamed([
      { type: 'progress', stage: 'route.solver', state: 'completed' },
      { type: 'result', response: route },
    ])
  );
  await expect(
    streamTripRoute({}, new AbortController().signal, () => {
      throw new Error('UI failed');
    })
  ).resolves.toEqual(route);
});
