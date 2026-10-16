import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import client from '../services/protectedRequest';
import { cognitoClient } from '../services/cognito';
import { getSession, signOut } from '../services/session';
import { fixtureSession, fixtureToken } from './sessionFixtures';
import { ensureChatCreated } from '../services/savedTrips';

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock('../services/cognito', () => ({ cognitoClient: { send: vi.fn() } }));
const base = 'https://api.example.test/';
const rejection = () => ({
  response: { status: 401, data: { detail: 'Invalid authentication token' } },
});
const renewed = () => ({
  AuthenticationResult: {
    AccessToken: fixtureToken('user', Date.now() / 1000 + 7200),
    IdToken: fixtureToken('user', Date.now() / 1000 + 7200, 'id'),
    RefreshToken: 'rotated',
  },
});
beforeEach(() => {
  signOut();
  sessionStorage.clear();
  vi.resetAllMocks();
  fixtureSession('user', undefined, 'refresh');
  import.meta.env.VITE_BACKEND_SERVER = base;
});
afterEach(() => {
  signOut();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('protected dispatch and bounded replay', () => {
  it('renews expired credentials once for concurrent CRUD and provider calls with matching bodies and headers', async () => {
    vi.useFakeTimers();
    vi.advanceTimersByTime(3600000);
    let resolve;
    cognitoClient.send.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        })
    );
    axios.post.mockResolvedValue({ data: {}, status: 200 });
    axios.get.mockResolvedValue({ data: {}, status: 200 });
    const operations = [
      client.post(base + 'chats/create/4', { PartitionKey: 'stale', ChatData: {} }),
      client.get(base + 'get-car-details'),
    ];
    expect(cognitoClient.send).toHaveBeenCalledTimes(1);
    resolve(renewed());
    await Promise.all(operations);
    const session = getSession();
    expect(axios.post.mock.calls[0][1].PartitionKey).toBe(session.accessToken);
    expect(axios.post.mock.calls[0][2].headers).toEqual({
      Authorization: `Bearer ${session.accessToken}`,
      'X-Cognito-Id-Token': session.idToken,
    });
  });
  it('reuses the newer session for concurrent stale-token 401s', async () => {
    let second;
    axios.get
      .mockRejectedValueOnce(rejection())
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            second = reject;
          })
      )
      .mockResolvedValue({ data: [] });
    cognitoClient.send.mockResolvedValue(renewed());
    const first = client.get(base + 'chats');
    const next = client.get(base + 'chats');
    await first;
    second(rejection());
    await next;
    expect(cognitoClient.send).toHaveBeenCalledTimes(1);
    expect(axios.get).toHaveBeenCalledTimes(4);
    expect(axios.get.mock.calls[3][1].headers.Authorization).toBe(
      `Bearer ${getSession().accessToken}`
    );
  });
  it.each(['get', 'post', 'put', 'delete'])(
    'retries a verified initial %s rejection at most once',
    async (method) => {
      const paths = {
        get: 'chats',
        post: 'generate-final-route',
        put: 'chats/update/4',
        delete: 'chats/delete/4',
      };
      axios[method].mockRejectedValue(rejection());
      cognitoClient.send.mockResolvedValue(renewed());
      await expect(
        client[method](base + paths[method], { partitionKey: getSession().accessToken })
      ).rejects.toMatchObject({ code: 'signin-required' });
      expect(axios[method]).toHaveBeenCalledTimes(2);
      expect(cognitoClient.send).toHaveBeenCalledTimes(1);
    }
  );
  it.each([null, 403, 500, 503, 401])(
    'does not replay uncertain failures or arbitrary status %s',
    async (status) => {
      const error = status
        ? { response: { status, data: { detail: 'Provider rejected request' } } }
        : new TypeError('network');
      axios.post.mockRejectedValue(error);
      await expect(client.post(base + 'generate-final-route', {})).rejects.toBe(error);
      expect(axios.post).toHaveBeenCalledTimes(1);
      expect(cognitoClient.send).not.toHaveBeenCalled();
    }
  );
  it('does not replay a mutation outside the audited endpoint set', async () => {
    axios.post.mockRejectedValue(rejection());
    await expect(client.post(base + 'unknown', {})).rejects.toMatchObject(rejection());
    expect(cognitoClient.send).not.toHaveBeenCalled();
  });
  it.each(['logout', 'switch'])(
    'discards an old-account HTTP response after %s',
    async (action) => {
      let resolve;
      axios.get.mockImplementation(
        () =>
          new Promise((done) => {
            resolve = done;
          })
      );
      const pending = client.get(base + 'chats');
      await vi.waitFor(() => expect(axios.get).toHaveBeenCalled());
      if (action === 'logout') signOut();
      else fixtureSession('other');
      resolve({ data: ['private'] });
      await expect(pending).rejects.toMatchObject({ code: 'session-changed' });
    }
  );
  it('rejects a previous-account closure before dispatch', async () => {
    const old = getSession().accessToken;
    fixtureSession('other');
    await expect(client.put(base + 'chats/update/4', { PartitionKey: old })).rejects.toMatchObject({
      code: 'session-changed',
    });
    expect(axios.put).not.toHaveBeenCalled();
  });
  it('keeps pending creation and readiness through same-account renewal', async () => {
    const old = getSession().accessToken;
    const owner = {};
    const data = { chatId: 4 };
    const chats = [{ id: 4, messages: [] }];
    let resolve;
    axios.post.mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        })
    );
    const first = ensureChatCreated(old, data, chats, owner);
    await vi.waitFor(() => expect(axios.post).toHaveBeenCalled());
    cognitoClient.send.mockResolvedValue(renewed());
    const { ensureSession } = await import('../services/session');
    await ensureSession({ rejectedToken: old });
    const second = ensureChatCreated(getSession().accessToken, data, chats, owner);
    resolve({ status: 200 });
    expect(await first).toBe(true);
    expect(await second).toBe(true);
    expect(await ensureChatCreated(old, data, chats, owner)).toBe(true);
    expect(axios.post).toHaveBeenCalledTimes(1);
  });
});
