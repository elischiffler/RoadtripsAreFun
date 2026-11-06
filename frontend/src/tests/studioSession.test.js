import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import axios from 'axios';
import { fixtureSession, fixtureToken } from './sessionFixtures';
import { cognitoClient } from '../services/cognito';
import { backendAuthConfig } from '../services/backendAuth';
import { signOut } from '../services/session';
import { getStudioSession, studioRequest, unlockStudio } from '../services/studioSession';

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock('../services/cognito', () => ({ cognitoClient: { send: vi.fn() } }));
beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
  fixtureSession('studio-owner');
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'original-visitor', expires_at: Date.now() / 1000 + 600 })
  );
});
afterEach(() => sessionStorage.clear());

it('sends both current Cognito credentials with Studio unlock and retains the visitor session boundary', async () => {
  axios.post.mockResolvedValue({
    data: { token: 'new-visitor', expires_at: Date.now() / 1000 + 600 },
  });
  await unlockStudio('password');
  expect(axios.post.mock.calls[0][2].headers).toEqual(backendAuthConfig().headers);
  expect(getStudioSession().token).toBe('new-visitor');
  axios.get.mockResolvedValue({ data: { runs: [] } });
  await studioRequest('get', 'runs');
  expect(axios.get.mock.calls[0][1].headers).toEqual({
    ...backendAuthConfig().headers,
    'X-Studio-Session': 'new-visitor',
  });
});

it('does not replay a Studio mutation after an authentication rejection or erase its visitor history on owner denial', async () => {
  axios.post.mockRejectedValue({
    response: { status: 401, data: { detail: 'Invalid authentication token' } },
  });
  await expect(studioRequest('post', 'run', { mode: 'live' })).rejects.toMatchObject({
    response: { status: 401 },
  });
  expect(axios.post).toHaveBeenCalledTimes(1);
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'original-visitor', expires_at: Date.now() / 1000 + 600 })
  );
  axios.get.mockRejectedValue({ response: { status: 403 } });
  await expect(studioRequest('get', 'runs')).rejects.toMatchObject({ response: { status: 403 } });
  expect(getStudioSession().token).toBe('original-visitor');
});

it('does not dispatch Studio requests after sign out', async () => {
  signOut();
  await expect(studioRequest('get', 'runs')).rejects.toBeDefined();
  expect(axios.get).not.toHaveBeenCalled();
});

it('renews Cognito credentials before dispatch without replacing the Studio visitor session', async () => {
  fixtureSession('studio-owner', undefined, 'refresh-token');
  sessionStorage.setItem('accessToken', fixtureToken('studio-owner', 1));
  sessionStorage.setItem('idToken', fixtureToken('studio-owner', 1, 'id'));
  const renewedAccess = fixtureToken('studio-owner', Date.now() / 1000 + 7200);
  const renewedIdentity = fixtureToken('studio-owner', Date.now() / 1000 + 7200, 'id');
  cognitoClient.send.mockResolvedValue({
    AuthenticationResult: {
      AccessToken: renewedAccess,
      IdToken: renewedIdentity,
    },
  });
  axios.get.mockResolvedValue({ data: { runs: [] } });
  await studioRequest('get', 'runs');
  expect(axios.get.mock.calls[0][1].headers).toEqual({
    Authorization: `Bearer ${renewedAccess}`,
    'X-Cognito-Id-Token': renewedIdentity,
    'X-Studio-Session': 'original-visitor',
  });
  expect(getStudioSession().token).toBe('original-visitor');
});
