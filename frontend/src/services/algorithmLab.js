import axios from 'axios';
import { backendAuthConfig } from './backendAuth';

export async function getLabPresets(signal) {
  const { data } = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}algorithm-lab/presets`, {
    ...backendAuthConfig(),
    signal,
  });
  return data;
}

export async function runLab(request, signal) {
  const { data } = await axios.post(
    `${import.meta.env.VITE_BACKEND_SERVER}algorithm-lab/run`,
    request,
    { ...backendAuthConfig(), signal }
  );
  return data;
}

export function labError(error) {
  if ([401, 403].includes(error.response?.status)) {
    return 'Algorithm Lab requires the authorized owner account. Sign in again to continue.';
  }
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc?.slice(1).join(' › ')}: ${item.msg}`).join('; ');
  }
  return typeof detail === 'string'
    ? detail
    : 'The run could not finish. Check your connection and try again.';
}
