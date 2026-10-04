import { useSyncExternalStore } from 'react';
import axios from 'axios';
import { backendAuthConfig } from './backendAuth';

export const ROUTING_ALGORITHM_KEY = 'devRoutingAlgorithm';
const EMPTY = Object.freeze({ canSelect: false, algorithms: [], defaultAlgorithm: null });
let credentials = '';
let state = EMPTY;
let expiresAt = 0;
let generation = 0;
const listeners = new Set();
let stopWatching;

function sessionKey() {
  return JSON.stringify([sessionStorage.getItem('accessToken'), sessionStorage.getItem('idToken')]);
}

// Local decoding only bounds UI lifetime. Eligibility always comes from the server.
function accessExpiry() {
  try {
    const token = sessionStorage.getItem('accessToken');
    const claims = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return typeof claims.exp === 'number' ? claims.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

function snapshot() {
  return credentials === sessionKey() && Date.now() < expiresAt ? state : EMPTY;
}

function emit() {
  listeners.forEach((listener) => listener());
}

export function invalidateRoutingSettings() {
  generation += 1;
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
  invalidateRoutingSettings();
  const key = sessionKey();
  credentials = key;
  const current = generation;
  const expiry = accessExpiry();
  if (expiry <= Date.now() || !sessionStorage.getItem('idToken')) return;
  try {
    const { data } = await axios.get(
      `${import.meta.env.VITE_BACKEND_SERVER}routing-settings`,
      backendAuthConfig()
    );
    if (current !== generation || key !== sessionKey()) return;
    expiresAt = Math.min(expiry, Number(data.expires_at) * 1000);
    if (data.can_select_algorithm !== true || expiresAt <= Date.now()) return;
    state = {
      canSelect: true,
      algorithms: data.algorithms,
      defaultAlgorithm: data.default,
      selectedAlgorithm: null,
    };
    emit();
  } catch {
    // Unknown or invalid sessions keep the picker unmounted.
  }
}

function watchSession() {
  // Subscribe while the header is mounted; auth changes invalidate synchronously.
  const checkSession = () => {
    if (credentials !== sessionKey()) void refreshRoutingSettings();
    else if (state !== EMPTY && Date.now() >= expiresAt) invalidateRoutingSettings();
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
