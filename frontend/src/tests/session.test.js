import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { cognitoClient } from '../services/cognito';
import {
  acceptSignIn,
  ensureSession,
  getSession,
  requireSignIn,
  safeReturnPath,
  signOut,
  watchSession,
} from '../services/session';
import { fixtureSession, fixtureToken } from './sessionFixtures';

vi.mock('../services/cognito', () => ({ cognitoClient: { send: vi.fn() } }));
const result = (refresh) => ({
  AuthenticationResult: {
    AccessToken: fixtureToken(),
    IdToken: fixtureToken('user', undefined, 'id'),
    ...(refresh ? { RefreshToken: refresh } : {}),
  },
});
beforeEach(() => {
  signOut();
  sessionStorage.clear();
  vi.clearAllMocks();
  vi.useFakeTimers();
});
afterEach(() => {
  signOut();
  vi.useRealTimers();
});
function expire() {
  fixtureSession('user', undefined, 'refresh');
  vi.advanceTimersByTime(3600000);
}

describe('Cognito session renewal', () => {
  it('uses a valid session without refreshing', async () => {
    fixtureSession('user', undefined, 'refresh');
    expect((await ensureSession()).owner).toBe('fixture:user');
    expect(cognitoClient.send).not.toHaveBeenCalled();
  });
  it.each(['expired', 'missing'])(
    'restores %s access credentials and coalesces callers',
    async (kind) => {
      expire();
      if (kind === 'missing') sessionStorage.removeItem('accessToken');
      let resolve;
      cognitoClient.send.mockImplementation(
        () =>
          new Promise((done) => {
            resolve = done;
          })
      );
      const one = ensureSession();
      const two = ensureSession();
      expect(cognitoClient.send).toHaveBeenCalledTimes(1);
      resolve(result());
      const [a, b] = await Promise.all([one, two]);
      expect(a.accessToken).toBe(b.accessToken);
      expect(a.refreshToken).toBe('refresh');
      expect(a.idToken).toBe(result().AuthenticationResult.IdToken);
    }
  );
  it('can restore using only a refresh token', async () => {
    sessionStorage.setItem('refreshToken', 'refresh');
    cognitoClient.send.mockResolvedValue(result());
    expect((await ensureSession()).owner).toBe('fixture:user');
  });
  it('renews within thirty seconds and emits one atomic update with a rotated token and device key', async () => {
    acceptSignIn({
      ...result().AuthenticationResult,
      RefreshToken: 'refresh',
      NewDeviceMetadata: { DeviceKey: 'device' },
    });
    vi.advanceTimersByTime(3571000);
    cognitoClient.send.mockResolvedValue(result('rotated'));
    const changed = vi.fn(() =>
      expect(getSession().idToken).toBe(result().AuthenticationResult.IdToken)
    );
    window.addEventListener('auth-changed', changed);
    await ensureSession();
    window.removeEventListener('auth-changed', changed);
    expect(changed).toHaveBeenCalledTimes(1);
    expect(getSession().refreshToken).toBe('rotated');
    expect(cognitoClient.send.mock.calls[0][0].input).toMatchObject({
      RefreshToken: 'refresh',
      DeviceKey: 'device',
    });
    expect(cognitoClient.send.mock.calls[0][0].constructor.name).toBe(
      'GetTokensFromRefreshTokenCommand'
    );
  });
  it.each([
    { AuthenticationResult: {} },
    { AuthenticationResult: { AccessToken: fixtureToken(), IdToken: fixtureToken('other') } },
    {
      AuthenticationResult: { AccessToken: fixtureToken('other'), IdToken: fixtureToken('other') },
    },
  ])('rejects incomplete or wrong-account results without partial writes', async (response) => {
    expire();
    const before = getSession();
    cognitoClient.send.mockResolvedValue(response);
    await expect(ensureSession()).rejects.toMatchObject({ code: 'invalid-renewal' });
    expect(getSession()).toMatchObject({
      accessToken: before.accessToken,
      idToken: before.idToken,
      refreshToken: 'refresh',
      status: 'unavailable',
    });
  });
  it('keeps credentials during an outage, throttles retries, and recovers later', async () => {
    expire();
    cognitoClient.send.mockRejectedValue(new TypeError('offline'));
    await expect(ensureSession()).rejects.toMatchObject({ code: 'renewal-unavailable' });
    await expect(ensureSession()).rejects.toMatchObject({ code: 'renewal-unavailable' });
    expect(cognitoClient.send).toHaveBeenCalledTimes(1);
    expect(getSession().refreshToken).toBe('refresh');
    vi.advanceTimersByTime(5000);
    cognitoClient.send.mockResolvedValue(result());
    expect((await ensureSession()).status).toBe('ready');
  });
  it.each(['NotAuthorizedException', 'UserNotFoundException'])(
    'requires sign-in once for %s',
    async (name) => {
      expire();
      const changed = vi.fn();
      window.addEventListener('auth-changed', changed);
      cognitoClient.send.mockRejectedValue({ name });
      await expect(ensureSession()).rejects.toMatchObject({ code: 'signin-required' });
      await expect(ensureSession()).rejects.toMatchObject({ code: 'signin-required' });
      window.removeEventListener('auth-changed', changed);
      expect(changed).toHaveBeenCalledTimes(1);
      expect(getSession().refreshToken).toBeNull();
      expect(getSession().owner).toBe('fixture:user');
    }
  );
  it.each(['logout', 'switch'])('discards a late refresh after %s', async (action) => {
    expire();
    let resolve;
    cognitoClient.send.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        })
    );
    const pending = ensureSession();
    if (action === 'logout') signOut();
    else fixtureSession('other');
    resolve(result('late'));
    await expect(pending).rejects.toMatchObject({ code: 'session-changed' });
    expect(getSession().owner).toBe(action === 'logout' ? null : 'fixture:other');
    expect(getSession().refreshToken).not.toBe('late');
  });
  it('restores on foreground return without repeated watchers or timers', async () => {
    fixtureSession('user', undefined, 'refresh');
    const stop = watchSession();
    vi.advanceTimersByTime(3600000);
    cognitoClient.send.mockResolvedValue(result());
    window.dispatchEvent(new Event('focus'));
    await vi.runAllTimersAsync();
    expect(cognitoClient.send).toHaveBeenCalledTimes(1);
    stop();
  });
  it('keeps selection for same-account sign-in and clears account artifacts for another account', () => {
    fixtureSession();
    sessionStorage.setItem('selectedChatId', '4');
    sessionStorage.setItem('roadtrips.agentChatId.4', 'conversation');
    requireSignIn();
    fixtureSession();
    expect(sessionStorage.getItem('selectedChatId')).toBe('4');
    fixtureSession('other');
    expect(sessionStorage.getItem('selectedChatId')).toBeNull();
    expect(sessionStorage.getItem('roadtrips.agentChatId.4')).toBeNull();
  });
  it.each(['//evil.example', '/chat/../../login', '/chat\\evil', 'https://evil.example', '/login'])(
    'rejects unsafe return path %s',
    (path) => expect(safeReturnPath(path)).toBe('/chat')
  );
  it('allows an application return path with query', () =>
    expect(safeReturnPath('/map?trip=4')).toBe('/map?trip=4'));
});
