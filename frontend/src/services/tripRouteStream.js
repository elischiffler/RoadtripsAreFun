import {
  ensureSession,
  getSession,
  isCurrentSession,
  requireSignIn,
  SessionError,
} from './session';
import { isAuthRejection, sessionRequest } from './protectedRequest';

const abortError = () => new DOMException('Trip planning was stopped.', 'AbortError');
const streamError = (status, detail) =>
  Object.assign(new Error('The planning service could not finish.'), {
    response: { status, data: detail ? { detail } : undefined },
  });

/** Authenticated account planning. Never replay a request after streaming begins. */
export async function streamTripRoute(payload, signal, onProgress) {
  const started = getSession();
  const controller = new AbortController();
  const cancel = () => controller.abort();
  const accountChanged = () => {
    if (!isCurrentSession(started)) cancel();
  };
  signal?.addEventListener('abort', cancel);
  window.addEventListener('auth-changed', accountChanged);
  if (signal?.aborted) cancel();
  let reader;
  let timer;
  const check = () => {
    if (!isCurrentSession(started)) throw new SessionError('session-changed');
    if (controller.signal.aborted) throw abortError();
  };
  const alive = () => {
    clearTimeout(timer);
    timer = setTimeout(cancel, 60000);
  };
  try {
    check();
    let session = await ensureSession();
    let response;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      check();
      alive();
      const { config } = sessionRequest(session, null, {
        headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
      });
      response = await fetch(`${import.meta.env.VITE_BACKEND_SERVER}generate-final-route/stream`, {
        method: 'POST',
        headers: config.headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      check();
      if (response.ok) break;
      const data = await response.json().catch(() => null);
      check();
      // Only an exact pre-stream Cognito verifier rejection proves no planning ran.
      if (!isAuthRejection({ status: response.status, data }))
        throw Object.assign(new Error('Trip planning was rejected.'), {
          response: { status: response.status, data },
        });
      if (attempt === 1) throw requireSignIn(started);
      session = await ensureSession({ rejectedToken: session.accessToken });
    }
    if (!response.headers.get('content-type')?.includes('application/x-ndjson') || !response.body)
      throw new Error(
        'Unexpected trip progress response. Please check your saved trips before retrying.'
      );
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    let received = 0;
    const consume = (line) => {
      check();
      const event = JSON.parse(line);
      if (!event || typeof event !== 'object') throw new Error('Invalid trip progress event.');
      if (event.type === 'error') throw streamError(event.status ?? 503);
      if (!['progress', 'heartbeat', 'result'].includes(event.type))
        throw new Error('Unexpected trip progress event.');
      if (event.type === 'progress' && typeof event.stage !== 'string')
        throw new Error('Invalid trip progress stage.');
      if (event.type === 'progress' || event.type === 'heartbeat') {
        try {
          onProgress?.(event);
        } catch {
          // Presentation errors must not discard a completed provider route.
        }
      }
      check();
      return event;
    };
    while (!controller.signal.aborted) {
      check();
      alive();
      const { value, done } = await reader.read();
      check();
      received += value?.byteLength ?? 0;
      if (received > 20 * 1024 * 1024) throw new Error('Trip progress response is too large.');
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
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
        throw new Error(
          'Trip progress ended without a result. Check your saved trips before retrying.'
        );
      }
      if (pending.length > 1024 * 1024) throw new Error('Trip progress event is too large.');
    }
    check();
    throw abortError();
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
    window.removeEventListener('auth-changed', accountChanged);
    await reader?.cancel().catch(() => {});
  }
}
