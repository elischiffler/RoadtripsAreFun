import { GetTokensFromRefreshTokenCommand } from '@aws-sdk/client-cognito-identity-provider';
import { cognitoClient } from './cognito';
import config from '../../config';

const TOKEN_KEYS = ['accessToken', 'idToken', 'refreshToken', 'deviceKey'];
const RENEW_BEFORE_MS = 30000;
let generation = 0;
let renewal;
let retryAfter = 0;
let lastFailure;
let status = 'idle';

// Advisory client claims schedule renewal and isolate UI state. The API verifies JWTs.
export function tokenClaims(token) {
  try {
    return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return null;
  }
}

export function tokenOwner(token) {
  const claims = tokenClaims(token);
  return typeof claims?.iss === 'string' &&
    typeof claims?.sub === 'string' &&
    claims.iss &&
    claims.sub
    ? `${claims.iss}:${claims.sub}`
    : null;
}

export function getSession() {
  const tokens = Object.fromEntries(TOKEN_KEYS.map((key) => [key, sessionStorage.getItem(key)]));
  return {
    ...tokens,
    owner:
      tokenOwner(tokens.accessToken) ||
      tokenOwner(tokens.idToken) ||
      sessionStorage.getItem('sessionOwner'),
    generation,
    status,
  };
}

export function isCurrentSession(session) {
  const current = getSession();
  return (
    current.generation === session.generation && (!session.owner || current.owner === session.owner)
  );
}

const usable = (token, margin = 0) => {
  const exp = tokenClaims(token)?.exp;
  return typeof exp === 'number' && Number.isFinite(exp) && exp * 1000 > Date.now() + margin;
};

export function hasUsableSession() {
  return status !== 'signin-required' && usable(getSession().accessToken);
}

function publish(nextStatus) {
  status = nextStatus;
  window.dispatchEvent(new Event('auth-changed'));
}

export class SessionError extends Error {
  constructor(code) {
    super(
      code === 'signin-required'
        ? 'Please sign in again to continue.'
        : 'Session renewal is temporarily unavailable. Please retry.'
    );
    this.code = code;
  }
}

function validateResult(result, expectedOwner) {
  const owner = tokenOwner(result?.AccessToken);
  if (
    !owner ||
    tokenClaims(result.AccessToken)?.token_use !== 'access' ||
    tokenClaims(result.IdToken)?.token_use !== 'id' ||
    (result.RefreshToken !== undefined &&
      (typeof result.RefreshToken !== 'string' || !result.RefreshToken)) ||
    !usable(result.AccessToken) ||
    !usable(result.IdToken) ||
    tokenOwner(result.IdToken) !== owner ||
    (expectedOwner && owner !== expectedOwner)
  ) {
    throw new SessionError('invalid-renewal');
  }
  return owner;
}

function writeTokens(result, refreshToken, deviceKey, owner) {
  // Synchronous writes, one event after the complete snapshot is available.
  sessionStorage.setItem('accessToken', result.AccessToken);
  sessionStorage.setItem('idToken', result.IdToken);
  if (refreshToken) sessionStorage.setItem('refreshToken', refreshToken);
  else sessionStorage.removeItem('refreshToken');
  if (deviceKey) sessionStorage.setItem('deviceKey', deviceKey);
  else sessionStorage.removeItem('deviceKey');
  sessionStorage.setItem('sessionOwner', owner);
}

function clearAccountStorage() {
  sessionStorage.removeItem('selectedChatId');
  Object.keys(sessionStorage)
    .filter((key) => key.startsWith('roadtrips.agentChatId.'))
    .forEach((key) => sessionStorage.removeItem(key));
}

export function acceptSignIn(result) {
  const owner = validateResult(result);
  if (getSession().owner !== owner) clearAccountStorage();
  generation += 1;
  renewal = undefined;
  retryAfter = 0;
  lastFailure = undefined;
  writeTokens(result, result.RefreshToken, result.NewDeviceMetadata?.DeviceKey, owner);
  publish('ready');
}

export function signOut() {
  generation += 1;
  renewal = undefined;
  retryAfter = 0;
  lastFailure = undefined;
  TOKEN_KEYS.forEach((key) => sessionStorage.removeItem(key));
  sessionStorage.removeItem('sessionOwner');
  clearAccountStorage();
  publish('signed-out');
}

export function requireSignIn(session = getSession()) {
  if (!isCurrentSession(session)) throw new SessionError('session-changed');
  if (status !== 'signin-required') {
    generation += 1;
    TOKEN_KEYS.forEach((key) => sessionStorage.removeItem(key));
    if (session.owner) sessionStorage.setItem('sessionOwner', session.owner);
    publish('signin-required');
  }
  return new SessionError('signin-required');
}

export async function ensureSession({ rejectedToken } = {}) {
  const session = getSession();
  const forced = rejectedToken && session.accessToken === rejectedToken;
  if (
    !forced &&
    usable(session.accessToken, session.refreshToken ? RENEW_BEFORE_MS : 0) &&
    (!session.idToken || usable(session.idToken, session.refreshToken ? RENEW_BEFORE_MS : 0))
  )
    return session;
  if (!session.refreshToken) throw requireSignIn(session);
  if (renewal?.generation === generation) return renewal.promise;
  if (Date.now() < retryAfter) throw lastFailure;
  const operation = { generation };
  renewal = operation;
  operation.promise = (async () => {
    try {
      const { AuthenticationResult } = await cognitoClient.send(
        new GetTokensFromRefreshTokenCommand({
          ClientId: config.clientId,
          RefreshToken: session.refreshToken,
          ...(session.deviceKey ? { DeviceKey: session.deviceKey } : {}),
        })
      );
      if (!isCurrentSession(session) || getSession().refreshToken !== session.refreshToken)
        throw new SessionError('session-changed');
      const owner = validateResult(AuthenticationResult, session.owner);
      writeTokens(
        AuthenticationResult,
        AuthenticationResult.RefreshToken || session.refreshToken,
        session.deviceKey,
        owner
      );
      retryAfter = 0;
      lastFailure = undefined;
      publish('ready');
      return getSession();
    } catch (error) {
      if (!isCurrentSession(session)) throw new SessionError('session-changed');
      if (['NotAuthorizedException', 'UserNotFoundException'].includes(error.name))
        throw requireSignIn(session);
      // Network, throttling, device/client configuration and malformed results are
      // recoverable here; never erase a possibly usable refresh token for these.
      lastFailure = error instanceof SessionError ? error : new SessionError('renewal-unavailable');
      retryAfter = Date.now() + 5000;
      publish('unavailable');
      throw lastFailure;
    } finally {
      if (renewal === operation) renewal = undefined;
    }
  })();
  return operation.promise;
}

// One watcher for the application, no per-component renewal timers.
export function watchSession() {
  const restore = () => {
    if (
      document.visibilityState !== 'hidden' &&
      (getSession().accessToken || getSession().refreshToken)
    )
      void ensureSession().catch(() => {});
  };
  window.addEventListener('focus', restore);
  document.addEventListener('visibilitychange', restore);
  restore();
  return () => {
    window.removeEventListener('focus', restore);
    document.removeEventListener('visibilitychange', restore);
  };
}

export const safeReturnPath = (path) =>
  typeof path === 'string' &&
  /^\/(chat|map|itinerary|settings|algorithm)(\?|$)/.test(path) &&
  !path.includes('\\')
    ? path
    : '/chat';
