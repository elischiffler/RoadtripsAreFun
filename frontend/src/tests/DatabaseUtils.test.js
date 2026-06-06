/**
 * DatabaseUtils — API call wrappers for chat CRUD.
 * axios is mocked so no real network calls happen.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

vi.mock('axios');

import { createChat, deleteChat, updateUserData } from '../pages/ChatPage/DatabaseUtils';

// Provide a fake VITE_BACKEND_SERVER so import.meta.env works in tests
beforeEach(() => {
  vi.clearAllMocks();
  // Vitest automatically processes import.meta.env via vite config;
  // set a predictable value via the env object if needed.
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});

const AUTH_TOKEN = 'test-token';
const CHAT_DATA = {
  chatId: 1,
  action: null,
  startConfirmed: null,
  endConfirmed: null,
  isComplete: false,
};
const CHAT_LOG = { id: 1, title: 'Test Trip', messages: [{ text: 'Hello', sender: 'bot' }] };

describe('createChat', () => {
  it('posts to chats/create/:chatId and returns null on success', async () => {
    axios.post.mockResolvedValueOnce({ status: 201, data: {} });
    const result = await createChat(AUTH_TOKEN, CHAT_DATA, CHAT_LOG);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post.mock.calls[0][0]).toMatch(/chats\/create\/1/);
    expect(result).toBeNull();
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

  it('returns null and does not throw on network error', async () => {
    axios.post.mockRejectedValueOnce(new Error('Network error'));
    const result = await createChat(AUTH_TOKEN, CHAT_DATA, CHAT_LOG);
    expect(result).toBeNull();
  });
});

describe('deleteChat', () => {
  it('calls DELETE chats/delete/:chatId', async () => {
    axios.delete.mockResolvedValueOnce({ status: 204 });
    await deleteChat(AUTH_TOKEN, 1);
    expect(axios.delete).toHaveBeenCalledTimes(1);
    expect(axios.delete.mock.calls[0][0]).toMatch(/chats\/delete\/1/);
  });

  it('returns null and does not throw on error', async () => {
    axios.delete.mockRejectedValueOnce(new Error('Server error'));
    const result = await deleteChat(AUTH_TOKEN, 1);
    expect(result).toBeNull();
  });
});

describe('updateUserData', () => {
  it('puts to chats/update/:chatId when the chat is found', async () => {
    axios.put.mockResolvedValueOnce({ status: 200, data: {} });
    const chats = [CHAT_LOG];
    await updateUserData(AUTH_TOKEN, CHAT_DATA, chats);
    expect(axios.put).toHaveBeenCalledTimes(1);
    expect(axios.put.mock.calls[0][0]).toMatch(/chats\/update\/1/);
  });

  it('returns null without calling put when chat is not found in array', async () => {
    const result = await updateUserData(AUTH_TOKEN, CHAT_DATA, []); // empty chats
    expect(axios.put).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });
});
