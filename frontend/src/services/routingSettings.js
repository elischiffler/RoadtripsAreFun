import { useSyncExternalStore } from 'react';
import axios from './protectedRequest';
import { ensureSession, getSession, tokenClaims } from './session';
import { backendAuthConfig } from './backendAuth';

export const ROUTING_ALGORITHM_KEY = 'devRoutingAlgorithm';
const EMPTY = Object.freeze({ canSelect: false, algorithms: [], defaultAlgorithm: null });
let credentials = '';
let state = EMPTY;
let expiresAt = 0;
let generation = 0;
const listeners = new Set();
let stopWatching;
let pending;
let owner = null;

function sessionKey() {
  return JSON.stringify([sessionStorage.getItem('accessToken'), sessionStorage.getItem('idToken')]);
}

// Local decoding only bounds UI lifetime. Eligibility always comes from the server.
function accessExpiry() {
  return Number(tokenClaims(getSession().accessToken)?.exp ?? 0) * 1000;
}

function snapshot() {
  return credentials === sessionKey() && Date.now() < expiresAt ? state : EMPTY;
}

function emit() {
  listeners.forEach((listener) => listener());
}

export function invalidateRoutingSettings() {
  generation += 1;
  pending = undefined;
  owner = null;
  credentials = '';
  state = EMPTY;
  expiresAt = 0;
  try {
    localStorage.removeItem(ROUTING_ALGORITHM_KEY);
  } catch {
    // Browser storage is optional; no saved value grants eligibility.
  }
  emit();
}

export async function refreshRoutingSettings() {
  const nextOwner = getSession().owner;
  if (owner !== nextOwner || !nextOwner || getSession().status === 'signin-required') {
    invalidateRoutingSettings();
    owner = nextOwner;
  }
  const key = sessionKey();
  if (pending?.key === key) return pending.promise;
  const current = ++generation;
  credentials = key;
  const selection = state.selectedAlgorithm;
  expiresAt = 0;
  try {
    localStorage.removeItem(ROUTING_ALGORITHM_KEY);
  } catch {
    /* Optional storage. */
  }
  emit();
  const operation = { key };
  pending = operation;
  operation.promise = (async () => {
    try {
      const session = await ensureSession();
      if (current !== generation || !session.idToken) return;
      const { data } = await axios.get(
        `${import.meta.env.VITE_BACKEND_SERVER}routing-settings`,
        backendAuthConfig()
      );
      if (current !== generation || session.owner !== getSession().owner) return;
      credentials = sessionKey();
      owner = session.owner;
      expiresAt = Math.min(accessExpiry(), Number(data.expires_at) * 1000);
      if (data.can_select_algorithm !== true || expiresAt <= Date.now()) {
        state = EMPTY;
        emit();
        return;
      }
      state = {
        canSelect: true,
        algorithms: data.algorithms,
        defaultAlgorithm: data.default,
        selectedAlgorithm: data.algorithms.includes(selection) ? selection : null,
      };
      emit();
    } catch {
      /* Unknown sessions keep the picker unmounted. */
    } finally {
      if (pending === operation) pending = undefined;
    }
  })();
  return operation.promise;
}

function watchSession() {
  // Subscribe while the header is mounted; auth changes invalidate synchronously.
  const checkSession = () => {
    if (credentials !== sessionKey()) void refreshRoutingSettings();
    else if (state !== EMPTY && Date.now() >= expiresAt) void refreshRoutingSettings();
    else emit();
  };
  const authChanged = () => void refreshRoutingSettings();
  window.addEventListener('auth-changed', authChanged);
  window.addEventListener('storage', checkSession);
  window.addEventListener('focus', checkSession);
  const timer = window.setInterval(checkSession, 1000);
  checkSession();
  return () => {
    window.clearInterval(timer);
    window.removeEventListener('auth-changed', authChanged);
    window.removeEventListener('storage', checkSession);
    window.removeEventListener('focus', checkSession);
  };
}

function subscribe(listener) {
  listeners.add(listener);
  if (listeners.size === 1) stopWatching = watchSession();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) stopWatching();
  };
}

export function useRoutingSettings() {
  return useSyncExternalStore(subscribe, snapshot);
}

export function getRoutingAlgorithm() {
  const capability = snapshot();
  return capability.canSelect && capability.algorithms.includes(capability.selectedAlgorithm)
    ? capability.selectedAlgorithm
    : null;
}

export function chooseRoutingAlgorithm(algorithm) {
  const capability = snapshot();
  if (capability.canSelect && capability.algorithms.includes(algorithm)) {
    state = { ...capability, selectedAlgorithm: algorithm };
    emit();
  }
}

export async function getFreshRoutingAlgorithm() {
  await ensureSession();
  if (credentials !== sessionKey() || Date.now() >= expiresAt) await refreshRoutingSettings();
  return getRoutingAlgorithm();
}
