import { studioRequest } from './studioSession';

export async function getStudioJob(id, signal) {
  return (await studioRequest('get', `jobs/${id}`, null, signal)).data;
}
export async function cancelStudioJob(id) {
  return (await studioRequest('delete', `jobs/${id}`)).data;
}

function pause(signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      reject(new DOMException('Disconnected', 'AbortError'));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', abort);
      resolve();
    }, 1500);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
  });
}

// Starting/resuming uses the same persisted UUID. A retry never starts another paid trip.
export async function runStudioJob(request, id, signal, onProgress) {
  let status = (await studioRequest('post', 'jobs', { id, run: request }, signal)).data;
  while (!signal?.aborted) {
    for (const event of status.progress ?? []) onProgress?.(event);
    if (status.state === 'complete') return status.result;
    if (status.state !== 'running') {
      throw Object.assign(new Error(status.message || 'The run could not finish.'), {
        terminal: true,
        response: {
          status: status.status ?? 409,
          data: {
            detail: status.message || 'The run could not finish. Open History for saved trips.',
          },
        },
      });
    }
    await pause(signal);
    status = await getStudioJob(id, signal);
  }
  throw new DOMException('Disconnected', 'AbortError');
}
