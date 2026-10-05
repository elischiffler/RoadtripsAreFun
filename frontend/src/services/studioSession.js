import axios from 'axios';

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
  try {
    const config = { ...studioConfig(signal), params };
    const url = `${import.meta.env.VITE_BACKEND_SERVER}studio/${path}`;
    return method === 'post'
      ? await axios.post(url, payload, config)
      : await axios.get(url, config);
  } catch (error) {
    if (error.response?.status === 401) clearStudioSession();
    throw error;
  }
}
