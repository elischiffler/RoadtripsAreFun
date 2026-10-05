import axios from 'axios';
import {
  ensureSession,
  getSession,
  isCurrentSession,
  requireSignIn,
  SessionError,
  tokenOwner,
} from './session';

export function sessionRequest(session, data, config = {}) {
  const headers = { ...config.headers };
  delete headers.Authorization;
  delete headers['X-Cognito-Id-Token'];
  headers.Authorization = `Bearer ${session.accessToken}`;
  if (session.idToken) headers['X-Cognito-Id-Token'] = session.idToken;
  const body = data ? { ...data } : data;
  for (const key of ['partitionKey', 'PartitionKey']) {
    if (body && Object.hasOwn(body, key)) body[key] = session.accessToken;
  }
  return { data: body, config: { ...config, headers } };
}

// Only the verifier's exact rejection is replayable. Provider and application
// 401s can occur after work, and must never trigger a second mutation/agent turn.
export const isAuthRejection = (response) =>
  response?.status === 401 && response.data?.detail === 'Invalid authentication token';

function replayable(url, method) {
  const base = import.meta.env.VITE_BACKEND_SERVER;
  if (!base || !url.startsWith(base)) return false;
  const path = url.slice(base.length).split('?')[0];
  return {
    get: /^(chats|routing-settings|get-initial-route|get-car-details|get-gas-price|get-location)$/,
    post: /^(chats\/create\/[^/]+|agent\/chat|generate-final-route|generate-itinerary)$/,
    put: /^chats\/update\/[^/]+$/,
    delete: /^chats\/delete\/[^/]+$/,
  }[method]?.test(path);
}

async function request(method, url, data, config) {
  const started = getSession();
  const suppliedOwner = tokenOwner(
    data?.partitionKey ||
      data?.PartitionKey ||
      config?.headers?.Authorization?.replace(/^Bearer /, '')
  );
  if (suppliedOwner && suppliedOwner !== started.owner) throw new SessionError('session-changed');
  let session = await ensureSession();
  if (!isCurrentSession(started)) throw new SessionError('session-changed');
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (!isCurrentSession(started)) throw new SessionError('session-changed');
    const fresh = sessionRequest(session, data, config);
    try {
      const response = await (method === 'get' || method === 'delete'
        ? axios[method](url, fresh.config)
        : axios[method](url, fresh.data, fresh.config));
      if (!isCurrentSession(started)) throw new SessionError('session-changed');
      return response;
    } catch (error) {
      if (!isCurrentSession(started)) throw new SessionError('session-changed');
      if (!isAuthRejection(error.response) || !replayable(url, method)) throw error;
      if (attempt === 1) throw requireSignIn(started);
      session = await ensureSession({ rejectedToken: session.accessToken });
    }
  }
}

export default {
  get: (url, config) => request('get', url, undefined, config),
  delete: (url, config) => request('delete', url, undefined, config),
  post: (url, data, config) => request('post', url, data, config),
  put: (url, data, config) => request('put', url, data, config),
};
