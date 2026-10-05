import {
  ensureSession,
  getSession,
  isCurrentSession,
  requireSignIn,
  SessionError,
  tokenOwner,
} from '../../services/session';
import { sessionRequest, isAuthRejection } from '../../services/protectedRequest';

/** Read one agent turn while forwarding diagnostic events as they arrive. */
export async function streamAgentMessage(url, data, config, onProgress) {
  const controller = new AbortController();
  const started = getSession();
  const changed = () => {
    if (!isCurrentSession(started)) controller.abort();
  };
  window.addEventListener('auth-changed', changed);
  const cancelled = () => controller.abort();
  config.signal?.addEventListener('abort', cancelled);
  if (config.signal?.aborted) controller.abort();
  let idleTimer;
  let reader;
  const report = (event) => {
    try {
      onProgress(event);
    } catch {
      // Diagnostics must never prevent a completed trip from reaching the UI.
    }
  };
  report({ type: 'progress', stage: 'client.request', state: 'started' });
  try {
    const suppliedOwner = tokenOwner(data?.partitionKey);
    if (suppliedOwner && suppliedOwner !== started.owner) throw new SessionError('session-changed');
    let session = await ensureSession();
    let response;
    idleTimer = setTimeout(() => controller.abort(), 45000);
    for (let attempt = 0; attempt < 2; attempt += 1) {
      if (!isCurrentSession(started)) throw new SessionError('session-changed');
      if (controller.signal.aborted) throw new Error('Cancelled');
      const fresh = sessionRequest(session, data, config);
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...fresh.config.headers },
        body: JSON.stringify(fresh.data),
        signal: controller.signal,
      });
      if (!isCurrentSession(started)) throw new SessionError('session-changed');
      if (
        response.status !== 401 ||
        url !== `${import.meta.env.VITE_BACKEND_SERVER}agent/chat/stream`
      )
        break;
      const detail = await response.json().catch(() => null);
      if (!isAuthRejection({ status: response.status, data: detail })) break;
      if (attempt === 1) throw requireSignIn(started);
      session = await ensureSession({ rejectedToken: session.accessToken });
    }
    if (!response.ok) {
      report({
        type: 'progress',
        stage: 'client.request',
        state: 'failed',
        status: response.status,
      });
      return { ok: false, status: response.status };
    }
    if (!response.headers.get('content-type')?.includes('application/x-ndjson')) {
      throw new Error('Unexpected progress response');
    }
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    while (!controller.signal.aborted) {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => controller.abort(), 45000);
      const { value, done } = await reader.read();
      if (!isCurrentSession(started)) throw new SessionError('session-changed');
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (pending.length > 20 * 1024 * 1024) throw new Error('Progress response too large');
      let boundary;
      while ((boundary = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, boundary).trim();
        pending = pending.slice(boundary + 1);
        if (!line) continue;
        if (!isCurrentSession(started)) throw new SessionError('session-changed');
        if (controller.signal.aborted) throw new Error('Progress request aborted');
        const event = JSON.parse(line);
        if (event.type === 'result') return event.response;
        if (event.type === 'error') return { ok: false, status: event.status ?? 503 };
        if (event.type === 'progress' || event.type === 'heartbeat') report(event);
      }
      if (done) throw new Error('Progress stream ended without a result');
    }
    throw new Error('Progress request aborted');
  } catch (error) {
    if (error instanceof SessionError) return { ok: false, status: null, sessionError: error.code };
    report({ type: 'progress', stage: 'client.connection', state: 'failed' });
    return { ok: false, status: null };
  } finally {
    window.removeEventListener('auth-changed', changed);
    config.signal?.removeEventListener('abort', cancelled);
    clearTimeout(idleTimer);
    await reader?.cancel().catch(() => {});
  }
}

export function createProgressLogger() {
  const started = performance.now();
  const active = new Map();
  let requestId = 'connecting';
  return (event) => {
    requestId = event.requestId ?? requestId;
    const seconds = ((performance.now() - started) / 1000).toFixed(1);
    const prefix = `[RouteProgress ${requestId} +${seconds}s]`;
    if (event.type === 'heartbeat') {
      const current = [...active.keys()].at(-1) ?? 'waiting for server';
      console.info(`${prefix} still running: ${current}`);
      return;
    }
    if (event.state === 'started') active.set(event.stage, true);
    else active.delete(event.stage);
    const log = event.state === 'failed' ? console.warn : console.info;
    log(`${prefix} ${event.stage} — ${event.state}`, event);
  };
}
