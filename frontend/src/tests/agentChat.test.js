import { fixtureSession } from './sessionFixtures';
/**
 * agentChat — API helper for the conversational chat agent.
 * axios is mocked so no real network calls happen.
 *
 * Contract under test (chat-agent-design.md §3):
 *   POST {VITE_BACKEND_SERVER}agent/chat
 *   body: { partitionKey, chatId (string), message, clientContext? }
 *   returns the AgentChatResponse on success, or a structured failure
 *   { ok: false, status } on error.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

vi.mock('axios');

import { sendAgentMessage } from '../pages/ChatPage/agentChat';

beforeEach(() => {
  vi.clearAllMocks();
  fixtureSession();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});

const AGENT_RESPONSE = {
  reply: 'Dropped your hotel budget and added Red Rocks near Denver.',
  toolsUsed: ['generate_final_route'],
  actions: [{ type: 'route_updated', chatId: '42' }],
  provider: 'groq',
  usage: { promptTokens: 100, completionTokens: 20 },
};

describe('sendAgentMessage', () => {
  it('sends both candidate selections in one request', async () => {
    axios.post.mockResolvedValueOnce({ data: AGENT_RESPONSE });
    const locationConfirmations = [
      { field: 'start_address', candidateId: 'start' },
      { field: 'destination_address', candidateId: 'end' },
    ];
    await sendAgentMessage({
      accessToken: 't',
      chatId: 42,
      message: 'Confirm both',
      locationConfirmations,
    });
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post.mock.calls[0][1].locationConfirmations).toEqual(locationConfirmations);
    expect(axios.post.mock.calls[0][1]).not.toHaveProperty('locationConfirmation');
  });
  it('sends an explicit location candidate selection', async () => {
    axios.post.mockResolvedValueOnce({ data: AGENT_RESPONSE });
    const locationConfirmation = { field: 'start_address', candidateId: 'server-candidate' };
    await sendAgentMessage({
      accessToken: 't',
      chatId: 42,
      message: 'Use the selected place',
      locationConfirmation,
    });
    expect(axios.post.mock.calls[0][1].locationConfirmation).toEqual(locationConfirmation);
  });
  it('posts to agent/chat with the correct body shape and returns data', async () => {
    axios.post.mockResolvedValueOnce({ status: 200, data: AGENT_RESPONSE });

    const result = await sendAgentMessage({
      accessToken: 'test-access-token',
      chatId: 42,
      message: 'make it cheaper',
      clientContext: { hasRoute: true, stops: 3, hotelBudget: 450 },
    });

    expect(axios.post).toHaveBeenCalledTimes(1);
    const [url, body] = axios.post.mock.calls[0];
    expect(url).toBe('http://localhost:8000/agent/chat');
    expect(body).toEqual({
      partitionKey: sessionStorage.getItem('accessToken'),
      chatId: '42', // coerced to string
      message: 'make it cheaper',
      clientContext: { hasRoute: true, stops: 3, hotelBudget: 450 },
    });
    expect(result).toEqual(AGENT_RESPONSE);
  });

  it('coerces chatId to a string', async () => {
    axios.post.mockResolvedValueOnce({ status: 200, data: AGENT_RESPONSE });
    await sendAgentMessage({ accessToken: 't', chatId: 7, message: 'hi' });
    expect(typeof axios.post.mock.calls[0][1].chatId).toBe('string');
    expect(axios.post.mock.calls[0][1].chatId).toBe('7');
  });

  it('omits clientContext when not provided', async () => {
    axios.post.mockResolvedValueOnce({ status: 200, data: AGENT_RESPONSE });
    await sendAgentMessage({ accessToken: 't', chatId: '1', message: 'hi' });
    expect(axios.post.mock.calls[0][1]).not.toHaveProperty('clientContext');
  });

  it('returns a structured failure (not throw) on network error', async () => {
    axios.post.mockRejectedValueOnce(new Error('Network error'));
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const result = await sendAgentMessage({ accessToken: 't', chatId: '1', message: 'hi' });
    // No axios.response on a raw network error → status is null.
    expect(result).toEqual({ ok: false, status: null });
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it('carries the HTTP status on a server error (e.g. 503)', async () => {
    axios.post.mockRejectedValueOnce({ response: { status: 503 } });
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const result = await sendAgentMessage({ accessToken: 't', chatId: '1', message: 'hi' });
    expect(result).toEqual({ ok: false, status: 503 });
    spy.mockRestore();
  });
});

it('opts into progress streaming without duplicating the chat request', async () => {
  const frame = JSON.stringify({ type: 'result', response: AGENT_RESPONSE }) + '\n';
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    headers: new Headers({ 'content-type': 'application/x-ndjson' }),
    body: {
      getReader: () => ({
        read: vi
          .fn()
          .mockResolvedValueOnce({ value: new TextEncoder().encode(frame), done: false }),
        cancel: vi.fn().mockResolvedValue(),
      }),
    },
  });
  vi.stubGlobal('fetch', fetch);
  try {
    const result = await sendAgentMessage({
      accessToken: 'test-access-token',
      chatId: 42,
      message: 'plan',
      onProgress: vi.fn(),
    });
    expect(result).toEqual(AGENT_RESPONSE);
    expect(fetch.mock.calls[0][0]).toBe('http://localhost:8000/agent/chat/stream');
    expect(JSON.parse(fetch.mock.calls[0][1].body).partitionKey).toBe(
      sessionStorage.getItem('accessToken')
    );
    expect(axios.post).not.toHaveBeenCalled();
  } finally {
    vi.unstubAllGlobals();
  }
});
