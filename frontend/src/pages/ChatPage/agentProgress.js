/** Read one agent turn while forwarding diagnostic events as they arrive. */
export async function streamAgentMessage(url, data, config, onProgress) {
  const controller = new AbortController();
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
    idleTimer = setTimeout(() => controller.abort(), 45000);
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...config.headers },
      body: JSON.stringify(data),
      signal: controller.signal,
    });
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
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (pending.length > 20 * 1024 * 1024) throw new Error('Progress response too large');
      let boundary;
      while ((boundary = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, boundary).trim();
        pending = pending.slice(boundary + 1);
        if (!line) continue;
        const event = JSON.parse(line);
        if (event.type === 'result') return event.response;
        if (event.type === 'error') return { ok: false, status: event.status ?? 503 };
        if (event.type === 'progress' || event.type === 'heartbeat') report(event);
      }
      if (done) throw new Error('Progress stream ended without a result');
    }
    throw new Error('Progress request aborted');
  } catch {
    report({ type: 'progress', stage: 'client.connection', state: 'failed' });
    return { ok: false, status: null };
  } finally {
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
