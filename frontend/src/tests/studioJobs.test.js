import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { studioRequest } from '../services/studioSession';
import { runStudioJob, cancelStudioJob, getStudioJob } from '../services/studioJobs';
vi.mock('../services/studioSession', () => ({ studioRequest: vi.fn() }));
beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

it('polls one job and returns its result without starting another run', async () => {
  studioRequest
    .mockResolvedValueOnce({
      data: { state: 'running', progress: [{ type: 'progress', stage: 'road' }] },
    })
    .mockResolvedValueOnce({ data: { state: 'complete', result: { route: { stops: [] } } } });
  const signal = new AbortController().signal;
  const progress = vi.fn();
  const done = runStudioJob({ inputs: 'trip' }, 'same-id', signal, progress);
  await vi.advanceTimersByTimeAsync(1500);
  expect(await done).toEqual({ route: { stops: [] } });
  expect(studioRequest.mock.calls.map(([method, path]) => [method, path])).toEqual([
    ['post', 'jobs'],
    ['get', 'jobs/same-id'],
  ]);
  expect(progress).toHaveBeenCalledWith({ type: 'progress', stage: 'road' });
});
it('disconnects browser polling without cancelling the server job', async () => {
  studioRequest.mockResolvedValue({ data: { state: 'running' } });
  const controller = new AbortController();
  const done = runStudioJob({}, 'one', controller.signal, vi.fn());
  const rejected = expect(done).rejects.toMatchObject({ name: 'AbortError' });
  await vi.advanceTimersByTimeAsync(1);
  controller.abort();
  await rejected;
  expect(studioRequest).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});
it('never auto-reruns interrupted work and uses DELETE only for explicit cancel', async () => {
  studioRequest.mockResolvedValueOnce({ data: { state: 'interrupted', message: 'Check History' } });
  await expect(
    runStudioJob({}, 'one', new AbortController().signal, vi.fn())
  ).rejects.toMatchObject({ terminal: true });
  studioRequest.mockResolvedValue({ data: { state: 'cancelled' } });
  await cancelStudioJob('one');
  expect(studioRequest).toHaveBeenLastCalledWith('delete', 'jobs/one');
  await getStudioJob('one', undefined);
  expect(studioRequest).toHaveBeenLastCalledWith('get', 'jobs/one', null, undefined);
});
