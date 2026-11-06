import { clearStudioSession, getStudioSession, studioConfig } from './studioSession';
import { ensureSession, isCurrentSession } from './session';
import { isAuthRejection } from './protectedRequest';

/** Consume actual worker progress and preserve the ordinary final run envelope. */
export async function streamStudioRun(request, signal, onProgress) {
  const session = await ensureSession();
  const config = studioConfig(signal);
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel);
  const sessionChanged = () => {
    if (!isCurrentSession(session)) cancel();
  };
  window.addEventListener('auth-changed', sessionChanged);
  if (signal?.aborted) cancel();
  let reader;
  let idleTimer;
  const errorWithStatus = (status, data) => {
    if (
      status === 401 &&
      !isAuthRejection({ status, data }) &&
      getStudioSession()?.token === config.headers['X-Studio-Session']
    )
      clearStudioSession();
    return Object.assign(new Error('Studio run failed'), { response: { status } });
  };
  const resetIdle = () => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(cancel, 45000);
  };
  try {
    if (controller.signal.aborted) throw new DOMException('Request aborted', 'AbortError');
    resetIdle();
    const response = await fetch(`${import.meta.env.VITE_BACKEND_SERVER}studio/run/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...config.headers },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const error = errorWithStatus(response.status, data);
      error.response.data = data;
      throw error;
    }
    if (!response.headers.get('content-type')?.includes('application/x-ndjson') || !response.body)
      throw new Error('Unexpected Studio progress response');
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    const consume = (line) => {
      if (!isCurrentSession(session)) throw new Error('Studio session changed');
      const event = JSON.parse(line);
      if (event.type === 'error') throw errorWithStatus(event.status ?? 503);
      if (event.type === 'progress' || event.type === 'heartbeat') {
        try {
          onProgress(event);
        } catch {
          // A presentation callback must not discard a completed provider trip.
        }
      }
      return event;
    };
    while (!controller.signal.aborted) {
      resetIdle();
      const { value, done } = await reader.read();
      if (controller.signal.aborted) throw new Error('Studio run cancelled');
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (pending.length > 20 * 1024 * 1024) throw new Error('Studio progress response too large');
      let boundary;
      while ((boundary = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, boundary).trim();
        pending = pending.slice(boundary + 1);
        if (!line) continue;
        const event = consume(line);
        if (event.type === 'result') return event.response;
      }
      if (done) {
        if (pending.trim()) {
          const event = consume(pending.trim());
          if (event.type === 'result') return event.response;
        }
        throw new Error('Studio progress ended without a result');
      }
    }
    throw new Error('Studio run cancelled');
  } finally {
    clearTimeout(idleTimer);
    signal?.removeEventListener('abort', cancel);
    window.removeEventListener('auth-changed', sessionChanged);
    await reader?.cancel().catch(() => {});
  }
}
