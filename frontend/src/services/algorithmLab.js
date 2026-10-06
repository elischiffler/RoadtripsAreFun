import { studioRequest } from './studioSession';
import { streamStudioRun } from './studioProgress';

export async function getLabPresets(signal) {
  return (await studioRequest('get', 'presets', null, signal)).data;
}

export async function runLab(request, signal, onProgress) {
  if (onProgress) return streamStudioRun(request, signal, onProgress);
  return (await studioRequest('post', 'run', request, signal)).data;
}

export function labError(error) {
  if ([401, 403].includes(error.response?.status)) {
    return 'Enter the Studio password to continue.';
  }
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc?.slice(1).join(' › ')}: ${item.msg}`).join('; ');
  }
  return typeof detail === 'string'
    ? detail
    : 'The run could not finish. Check your connection and try again.';
}

export async function getLabRuns(signal, offset = 0) {
  const { data } = await studioRequest('get', 'runs', null, signal, { limit: 50, offset });
  if (!Array.isArray(data.runs) || !Array.isArray(data.groups))
    throw new Error('Invalid run history response');
  return data;
}

export async function getLabResult(runId, signal) {
  return (await studioRequest('get', `runs/${runId}/result`, null, signal)).data;
}
