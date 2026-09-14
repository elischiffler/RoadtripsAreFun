/**
 * agentChat — API helper for the conversational chat agent.
 * axios is mocked so no real network calls happen.
 *
 * Contract under test (chat-agent-design.md §3):
 *   POST {VITE_BACKEND_SERVER}agent/chat
 *   body: { partitionKey, chatId (string), message, clientContext? }
 *   returns AgentChatResponse or null on error.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

vi.mock('axios');

import { sendAgentMessage } from '../pages/ChatPage/agentChat';

beforeEach(() => {
  vi.clearAllMocks();
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
      partitionKey: 'test-access-token',
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
