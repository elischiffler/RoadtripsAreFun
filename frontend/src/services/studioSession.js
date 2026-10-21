import axios from 'axios';
import { clearStudioWorkspace } from './studioWorkspace';
import { clearResearchCache } from './studioResearchCache';

const KEY = 'studioSession';
export function getStudioSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(KEY));
    return session?.token && session.expires_at > Date.now() / 1000 ? session : null;
  } catch {
    return null;
  }
}
export function clearStudioSession() {
  sessionStorage.removeItem(KEY);
  clearStudioWorkspace();
  clearResearchCache();
  window.dispatchEvent(new Event('studio-access-changed'));
}
export async function unlockStudio(password) {
  const { data } = await axios.post(`${import.meta.env.VITE_BACKEND_SERVER}studio/access`, {
    password,
  });
  if (typeof data.token !== 'string' || !(data.expires_at > Date.now() / 1000))
    throw new Error('Invalid Studio session response');
  sessionStorage.setItem(KEY, JSON.stringify(data));
  window.dispatchEvent(new Event('studio-access-changed'));
}
export function studioConfig(signal) {
  return { signal, headers: { 'X-Studio-Session': getStudioSession()?.token || '' } };
}
export async function studioRequest(method, path, payload, signal, params) {
  const config = { ...studioConfig(signal), params };
  try {
    const url = `${import.meta.env.VITE_BACKEND_SERVER}studio/${path}`;
    if (method === 'post') return await axios.post(url, payload, config);
    if (method === 'delete') return await axios.delete(url, config);
    return await axios.get(url, config);
  } catch (error) {
    if (
      error.response?.status === 401 &&
      getStudioSession()?.token === config.headers['X-Studio-Session']
    )
      clearStudioSession();
    throw error;
  }
}
