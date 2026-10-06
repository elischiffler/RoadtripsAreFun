import { ReadableStream } from 'node:stream/web';
import { TextEncoder } from 'node:util';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { streamStudioRun } from '../services/studioProgress';
import { getStudioSession } from '../services/studioSession';
import StudioProgress from '../pages/AlgorithmLab/StudioProgress';

beforeEach(() => {
  sessionStorage.clear();
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'visitor', expires_at: Date.now() / 1000 + 600 })
  );
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function response(events, newline = true) {
  const bytes = new TextEncoder().encode(
    events.map((event) => JSON.stringify(event)).join('\n') + (newline ? '\n' : '')
  );
  return {
    ok: true,
    headers: new Headers({ 'content-type': 'application/x-ndjson' }),
    body: new ReadableStream({
      start(controller) {
        for (let offset = 0; offset < bytes.length; offset += 7)
          controller.enqueue(bytes.slice(offset, offset + 7));
        controller.close();
      },
    }),
  };
}

it('streams split Unicode frames and heartbeats before preserving the final run result', async () => {
  const events = [
    {
      type: 'progress',
      stage: 'attractions.collected',
      state: 'completed',
      name: 'Musée',
      collected: 2,
    },
    { type: 'heartbeat' },
    { type: 'result', response: { route: { stops: [] }, run_record: { saved: true } } },
  ];
  const fetch = vi.fn().mockResolvedValue(response(events, false));
  vi.stubGlobal('fetch', fetch);
  const report = vi.fn();
  const request = { mode: 'live', inputs: { num_stops: 2 } };
  const result = await streamStudioRun(request, undefined, report);
  expect(report.mock.calls.map(([event]) => event)).toEqual(events.slice(0, 2));
  expect(result).toEqual(events[2].response);
  expect(fetch.mock.calls[0][0]).toBe('http://localhost:8000/studio/run/stream');
  expect(fetch.mock.calls[0][1].headers).toEqual({
    'Content-Type': 'application/json',
    'X-Studio-Session': 'visitor',
  });
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
});

it('rejects interrupted streams and structured backend errors', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(response([{ type: 'heartbeat' }]))
      .mockResolvedValueOnce(response([{ type: 'error', status: 503 }]))
  );
  await expect(streamStudioRun({}, undefined, vi.fn())).rejects.toThrow('without a result');
  await expect(streamStudioRun({}, undefined, vi.fn())).rejects.toMatchObject({
    response: { status: 503 },
  });
});

it('relocks on authentication failure while preserving structured validation details', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Enter password' }),
    })
  );
  await expect(streamStudioRun({}, undefined, vi.fn())).rejects.toMatchObject({
    response: { status: 401, data: { detail: 'Enter password' } },
  });
  expect(getStudioSession()).toBeNull();
});

it('does not invalidate a newer Studio session after an old request is rejected', async () => {
  let rejectOld;
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          rejectOld = resolve;
        })
    )
  );
  const pending = streamStudioRun({}, undefined, vi.fn());
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'new-visitor', expires_at: Date.now() / 1000 + 600 })
  );
  rejectOld({ ok: false, status: 401, json: async () => ({}) });
  await expect(pending).rejects.toMatchObject({ response: { status: 401 } });
  expect(getStudioSession().token).toBe('new-visitor');
});

it('forwards cancellation and does not render a late completed response', async () => {
  const controller = new AbortController();
  const fetch = vi.fn().mockImplementation(
    (_url, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () =>
          reject(new DOMException('Cancelled', 'AbortError'))
        );
      })
  );
  vi.stubGlobal('fetch', fetch);
  const pending = streamStudioRun({}, controller.signal, vi.fn());
  controller.abort();
  await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

it('keeps a completed result when a progress presentation callback fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      response([
        { type: 'progress', stage: 'studio.inputs' },
        { type: 'result', response: { route: {} } },
      ])
    )
  );
  expect(
    await streamStudioRun({}, undefined, () => {
      throw new Error('render failed');
    })
  ).toEqual({ route: {} });
});

it('shows actual candidate counts and explains the distinction between AI ratings and provider facts', () => {
  const view = render(
    <StudioProgress
      events={[
        { type: 'progress', stage: 'route.gathering', state: 'started' },
        {
          type: 'progress',
          stage: 'attractions.ratings',
          state: 'started',
          query: 2,
          queries: 6,
          candidates: 4,
        },
      ]}
    />
  );
  expect(screen.getByRole('status')).toHaveTextContent('Route sample 2 of 6');
  expect(screen.getByRole('status')).toHaveTextContent('4 provider-verified places');
  expect(screen.getByRole('list', { name: 'Live planning stages' })).toHaveTextContent(
    'Ratings are estimates, not provider facts'
  );
  expect(screen.getByRole('list')).toHaveTextContent(
    'minimizes route-gap deviation plus detour time'
  );
  view.rerender(
    <StudioProgress
      events={[
        { type: 'progress', stage: 'route.gathering', state: 'completed' },
        {
          type: 'progress',
          stage: 'route.model',
          state: 'completed',
          eligible: 3,
          candidates: 8,
          threshold: 0.6,
          slots: 2,
          requestedStops: 2,
        },
      ]}
    />
  );
  expect(screen.getByRole('status')).toHaveTextContent('3 of 8 candidates');
  expect(screen.getByText('Collect and score nearby places').closest('li')).toHaveAttribute(
    'data-state',
    'completed'
  );
  expect(screen.getByText('Build the dated itinerary').closest('li')).toHaveAttribute(
    'data-state',
    'pending'
  );
});

it('does not advance phases from heartbeats or infer hotel work that has not begun', () => {
  render(
    <StudioProgress
      events={[
        { type: 'progress', stage: 'studio.initial_route', state: 'started' },
        { type: 'progress', stage: 'mapbox.request', state: 'started' },
        { type: 'heartbeat' },
      ]}
    />
  );
  expect(screen.getByRole('heading')).toHaveTextContent('Get the starting road route');
  expect(screen.getByText('Schedule visits and overnight stays').closest('li')).toHaveAttribute(
    'data-state',
    'pending'
  );
});

it('keeps endpoint completion when a nested road provider reports later', () => {
  render(
    <StudioProgress
      events={[
        { type: 'progress', stage: 'studio.endpoints', state: 'completed' },
        { type: 'progress', stage: 'mapbox.request', state: 'completed' },
        { type: 'progress', stage: 'studio.initial_route', state: 'completed' },
        {
          type: 'progress',
          stage: 'route.samples',
          state: 'completed',
          queries: 6,
          requestedStops: 2,
        },
        { type: 'progress', stage: 'route.gathering', state: 'started' },
      ]}
    />
  );
  expect(screen.getByText('Locate the cities').closest('li')).toHaveAttribute(
    'data-state',
    'completed'
  );
  expect(screen.getByText('Get the starting road route').closest('li')).toHaveAttribute(
    'data-state',
    'completed'
  );
});
