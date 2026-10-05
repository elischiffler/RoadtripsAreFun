import { afterEach, expect, it, vi } from 'vitest';
import { cognitoClient } from '../services/cognito';
import { ensureSession, getSession, signOut } from '../services/session';
import { fixtureSession } from './sessionFixtures';

vi.mock('../services/cognito', () => ({ cognitoClient: { send: vi.fn() } }));
afterEach(() => {
  signOut();
  vi.useRealTimers();
});
it('bounds a hung renewal, retains credentials and does not retry automatically', async () => {
  signOut();
  fixtureSession('user', undefined, 'fixture-refresh');
  vi.useFakeTimers();
  vi.advanceTimersByTime(3600000);
  cognitoClient.send.mockImplementation(
    (command, { abortSignal }) =>
      new Promise((resolve, reject) => {
        abortSignal.addEventListener('abort', () => reject(new Error('aborted')));
      })
  );
  const outcome = ensureSession().catch((error) => error);
  await vi.advanceTimersByTimeAsync(15000);
  expect(await outcome).toMatchObject({ code: 'renewal-unavailable' });
  expect(getSession()).toMatchObject({ refreshToken: 'fixture-refresh', status: 'unavailable' });
  expect(cognitoClient.send).toHaveBeenCalledTimes(1);
});
