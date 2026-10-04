import { ReadableStream } from 'node:stream/web';
import { TextEncoder } from 'node:util';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { streamAgentMessage, createProgressLogger } from '../pages/ChatPage/agentProgress';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function response(events) {
  const bytes = new TextEncoder().encode(
    events.map((event) => JSON.stringify(event)).join('\n') + '\n'
  );
  return {
    ok: true,
    headers: new Headers({ 'content-type': 'application/x-ndjson' }),
    body: new ReadableStream({
      start(controller) {
        for (let offset = 0; offset < bytes.length; offset += 7)
          controller.enqueue(bytes.slice(offset, offset + 7));
        controller.close();
      },
    }),
  };
}

describe('agent progress stream', () => {
  it('handles split frames and unicode while preserving auth and final response', async () => {
    const progress = vi.fn();
    const fetch = vi
      .fn()
      .mockResolvedValue(
        response([
          { type: 'progress', stage: 'hotels.lookup', state: 'started' },
          { type: 'heartbeat' },
          { type: 'result', response: { reply: 'Hôtel ready', actions: [] } },
        ])
      );
    vi.stubGlobal('fetch', fetch);
    const result = await streamAgentMessage(
      '/stream',
      { message: 'plan' },
      { headers: { Authorization: 'Bearer fixture', 'X-Cognito-Id-Token': 'identity' } },
      progress
    );
    expect(result.reply).toBe('Hôtel ready');
    expect(progress).toHaveBeenCalledWith({ type: 'heartbeat' });
    expect(fetch.mock.calls[0][1].headers).toMatchObject({
      Authorization: 'Bearer fixture',
      'X-Cognito-Id-Token': 'identity',
    });
  });

  it('preserves structured server errors and detects interrupted streams', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(response([{ type: 'error', status: 503 }]))
        .mockResolvedValueOnce(response([{ type: 'heartbeat' }]))
    );
    expect(await streamAgentMessage('/stream', {}, {}, vi.fn())).toEqual({
      ok: false,
      status: 503,
    });
    expect(await streamAgentMessage('/stream', {}, {}, vi.fn())).toEqual({
      ok: false,
      status: null,
    });
  });

  it('diagnostic callback failures do not lose the final result', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          response([{ type: 'heartbeat' }, { type: 'result', response: { reply: 'ready' } }])
        )
    );
    expect(
      await streamAgentMessage('/stream', {}, {}, () => {
        throw new Error('logging');
      })
    ).toEqual({ reply: 'ready' });
  });

  it('logs the current stage and elapsed waiting time', () => {
    const log = vi.spyOn(console, 'info').mockImplementation(() => {});
    const logger = createProgressLogger();
    logger({ type: 'progress', requestId: 'test', stage: 'hotels.lookup', state: 'started' });
    logger({ type: 'heartbeat' });
    expect(log.mock.calls[1][0]).toContain('still running: hotels.lookup');
    expect(log.mock.calls[1][0]).toContain('RouteProgress test +');
  });
});
