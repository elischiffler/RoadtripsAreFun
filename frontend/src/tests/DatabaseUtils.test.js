import { fixtureSession } from './sessionFixtures';
/**
 * DatabaseUtils — API call wrappers for chat CRUD.
 * axios is mocked so no real network calls happen.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

vi.mock('axios');

import {
  createChat,
  ensureChatCreated,
  deleteChat,
  initializeUserData,
  updateUserData,
} from '../pages/ChatPage/DatabaseUtils';

// Provide a fake VITE_BACKEND_SERVER so import.meta.env works in tests
beforeEach(() => {
  vi.clearAllMocks();
  AUTH_TOKEN = fixtureSession().AccessToken;
  // Vitest automatically processes import.meta.env via vite config;
  // set a predictable value via the env object if needed.
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});

let AUTH_TOKEN;
const CHAT_DATA = {
  chatId: 1,
  action: null,
  startConfirmed: null,
  endConfirmed: null,
  isComplete: false,
};
const CHAT_LOG = { id: 1, title: 'Test Trip', messages: [{ text: 'Hello', sender: 'bot' }] };

describe('createChat', () => {
  it('posts to chats/create/:chatId and returns true on success', async () => {
    axios.post.mockResolvedValueOnce({ status: 201, data: {} });
    const result = await createChat(AUTH_TOKEN, CHAT_DATA, CHAT_LOG);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post.mock.calls[0][0]).toMatch(/chats\/create\/1/);
    expect(result).toBe(true);
  });

  it('strips loading bubbles before posting', async () => {
    axios.post.mockResolvedValueOnce({ status: 201, data: {} });
    const logWithLoader = {
      ...CHAT_LOG,
      messages: [...CHAT_LOG.messages, { type: 'loading-chat' }],
    };
    await createChat(AUTH_TOKEN, CHAT_DATA, logWithLoader);
    const body = axios.post.mock.calls[0][1];
    expect(body.ChatLog.messages.every((m) => m.type !== 'loading-chat')).toBe(true);
  });

  it('returns false and does not throw on network error', async () => {
    axios.post.mockRejectedValueOnce(new Error('Network error'));
    const result = await createChat(AUTH_TOKEN, CHAT_DATA, CHAT_LOG);
    expect(result).toBe(false);
  });
});

describe('deleteChat', () => {
  it('calls DELETE chats/delete/:chatId', async () => {
    axios.delete.mockResolvedValueOnce({ status: 204 });
    await deleteChat(AUTH_TOKEN, 1);
    expect(axios.delete).toHaveBeenCalledTimes(1);
    expect(axios.delete.mock.calls[0][0]).toMatch(/chats\/delete\/1/);
    expect(axios.delete.mock.calls[0][1]).toEqual({
      headers: {
        Authorization: `Bearer ${AUTH_TOKEN}`,
        'X-Cognito-Id-Token': sessionStorage.getItem('idToken'),
      },
    });
  });

  it('returns null and does not throw on error', async () => {
    axios.delete.mockRejectedValueOnce({
      response: { status: 403 },
      config: { headers: { Authorization: `Bearer ${AUTH_TOKEN}` } },
    });
    const result = await deleteChat(AUTH_TOKEN, 1);
    expect(result).toBeNull();
    expect(JSON.stringify(console.error.mock.calls)).not.toContain(AUTH_TOKEN);
  });
});

describe('initializeUserData', () => {
  it('restores pending candidate IDs with the saved profile', async () => {
    const tripProfile = {
      pending_locations: {
        start_address: {
          query: 'SLO',
          candidates: [{ id: 'pending-id', address: 'Salem, Illinois' }],
        },
      },
    };
    axios.get.mockResolvedValueOnce({ data: [[{ chatId: 1, tripProfile }, CHAT_LOG]] });
    const result = await initializeUserData(AUTH_TOKEN);
    expect(result.UserData.chatlogs.getChatDataById(1).tripProfile).toEqual(tripProfile);
  });
  it('restores the agent conversation ID from saved ChatData', async () => {
    axios.get.mockResolvedValueOnce({
      data: [[{ chatId: 1, agentChatId: 'saved-agent-id' }, CHAT_LOG]],
    });
    const result = await initializeUserData(AUTH_TOKEN);
    expect(result.UserData.chatlogs.getChatDataById(1).agentChatId).toBe('saved-agent-id');
  });

  it('sends the token only in Authorization, never URL parameters', async () => {
    axios.get.mockResolvedValueOnce({ data: [] });
    const result = await initializeUserData(AUTH_TOKEN);
    expect(result).not.toBeNull();
    expect(axios.get.mock.calls[0][0]).toMatch(/\/chats$/);
    expect(axios.get.mock.calls[0][1]).toEqual({
      headers: {
        Authorization: `Bearer ${AUTH_TOKEN}`,
        'X-Cognito-Id-Token': sessionStorage.getItem('idToken'),
      },
    });
  });

  it('does not log Axios request headers on failure', async () => {
    axios.get.mockRejectedValueOnce({
      response: { status: 403 },
      config: { headers: { Authorization: `Bearer ${AUTH_TOKEN}` } },
    });
    expect(await initializeUserData(AUTH_TOKEN)).toBeNull();
    expect(JSON.stringify(console.error.mock.calls)).not.toContain(AUTH_TOKEN);
  });
});

describe('updateUserData', () => {
  it('creates the owner-scoped chat when the first update finds no row', async () => {
    axios.put.mockRejectedValueOnce({
      response: { status: 404, data: { detail: 'Chat not found' } },
    });
    axios.post.mockResolvedValueOnce({ status: 200, data: {} });
    const chats = [
      {
        ...CHAT_LOG,
        messages: [...CHAT_LOG.messages, { type: 'loading-chat' }],
      },
    ];

    expect(await updateUserData(AUTH_TOKEN, CHAT_DATA, chats)).toBe(true);
    expect(axios.put).toHaveBeenCalledTimes(1);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post.mock.calls[0][0]).toMatch(/chats\/create\/1/);
    expect(axios.post.mock.calls[0][1]).toEqual({
      PartitionKey: AUTH_TOKEN,
      ChatData: CHAT_DATA,
      ChatLog: CHAT_LOG,
    });
  });

  it('puts to chats/update/:chatId when the chat is found', async () => {
    axios.put.mockResolvedValueOnce({ status: 200, data: {} });
    const chats = [CHAT_LOG];
    expect(await updateUserData(AUTH_TOKEN, CHAT_DATA, chats)).toBe(true);
    expect(axios.put).toHaveBeenCalledTimes(1);
    expect(axios.put.mock.calls[0][0]).toMatch(/chats\/update\/1/);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('does not create on authorization failures', async () => {
    axios.put.mockRejectedValueOnce({ response: { status: 403 } });
    expect(await updateUserData(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG])).toBe(false);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('reports a failed create after a missing-row update', async () => {
    axios.put.mockRejectedValueOnce({ response: { status: 404 } });
    axios.post.mockRejectedValueOnce({ response: { status: 503 } });
    expect(await updateUserData(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG])).toBe(false);
  });

  it('returns false without calling put when chat is not found in array', async () => {
    const result = await updateUserData(AUTH_TOKEN, CHAT_DATA, []); // empty chats
    expect(axios.put).not.toHaveBeenCalled();
    expect(result).toBe(false);
  });
});

describe('chat creation lifecycle', () => {
  it('shares creation across remounts and blocks PUT until POST completes', async () => {
    const owner = {};
    let finish;
    axios.post.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    );
    axios.put.mockResolvedValueOnce({ status: 200 });
    const creation = ensureChatCreated(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG], owner);
    const save = updateUserData(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG], owner);
    await vi.waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
    expect(axios.put).not.toHaveBeenCalled();
    finish({ status: 200 });
    expect(await creation).toBe(true);
    expect(await save).toBe(true);
    await ensureChatCreated(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG], owner);
    expect(axios.post).toHaveBeenCalledTimes(1);
  });
  it('retries creation without PUT and isolates accounts', async () => {
    const owner = {};
    axios.post.mockRejectedValueOnce(new Error('offline'));
    expect(await updateUserData(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG], owner)).toBe(false);
    expect(axios.put).not.toHaveBeenCalled();
    axios.post.mockResolvedValue({ status: 200 });
    expect(await ensureChatCreated(AUTH_TOKEN, CHAT_DATA, [CHAT_LOG], owner)).toBe(true);
    const other = fixtureSession('other').AccessToken;
    expect(await ensureChatCreated(other, CHAT_DATA, [CHAT_LOG], owner)).toBe(true);
    expect(axios.post).toHaveBeenCalledTimes(3);
  });
  it('recognizes restored rows without recreating them', async () => {
    axios.get.mockResolvedValueOnce({ data: [[CHAT_DATA, CHAT_LOG]] });
    const restored = await initializeUserData(AUTH_TOKEN);
    expect(
      await ensureChatCreated(AUTH_TOKEN, CHAT_DATA, restored.chats, restored.UserData.chatlogs)
    ).toBe(true);
    expect(axios.post).not.toHaveBeenCalled();
  });
});

it('keeps created rows across token refresh and forgets deleted rows', async () => {
  const owner = {};
  const token = (expiration) =>
    `header.${btoa(JSON.stringify({ iss: 'fixture', sub: 'user', exp: expiration }))}.signature`;
  axios.post.mockResolvedValue({ status: 200 });
  expect(await ensureChatCreated(token(1), CHAT_DATA, [CHAT_LOG], owner)).toBe(true);
  expect(await ensureChatCreated(token(2), CHAT_DATA, [CHAT_LOG], owner)).toBe(true);
  expect(axios.post).toHaveBeenCalledTimes(1);
  axios.delete.mockResolvedValueOnce({ status: 200 });
  await deleteChat(token(2), 1, owner);
  expect(await ensureChatCreated(token(2), CHAT_DATA, [CHAT_LOG], owner)).toBe(true);
  expect(axios.post).toHaveBeenCalledTimes(2);
});
