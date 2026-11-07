import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import client from '../services/protectedRequest';
import { createChat, ensureChatCreated, updateUserData } from '../services/savedTrips';
import { fixtureSession } from './sessionFixtures';
import { getSession, signOut } from '../services/session';
vi.mock('../services/protectedRequest', () => ({
  default: { post: vi.fn(), put: vi.fn(), get: vi.fn(), delete: vi.fn() },
}));
const collision = () => ({
  response: { status: 409, data: { detail: 'Trip ID belongs to a different planning request' } },
});
const planned = () => ({
  chatId: 8,
  agentChatId: 'planning-a',
  route: { name: 'Completed route' },
});
const log = () => ({ id: 8, title: 'New trip', messages: [] });
let token;
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  token = fixtureSession().AccessToken;
  import.meta.env.VITE_BACKEND_SERVER = 'https://api.example.test/';
});
afterEach(() => vi.restoreAllMocks());
function randomIds(...ids) {
  return vi.spyOn(crypto, 'getRandomValues').mockImplementation((words) => {
    const value = ids.shift() ?? [2, 500];
    words.set(value);
    return words;
  });
}
it('retries only a confirmed guided collision with a fresh numeric ID and keeps snapshot/history aligned', async () => {
  const data = planned(),
    record = log(),
    existing = { id: 7, title: 'Existing trip', messages: [{ text: 'History', sender: 'bot' }] };
  const owner = { chatdata: [{ chatId: 7, agentChatId: 'existing' }] },
    chats = [existing, record];
  const random = randomIds([0, 7], [1, 99]);
  client.post.mockRejectedValueOnce(collision()).mockResolvedValueOnce({ status: 201 });
  expect(await ensureChatCreated(token, data, chats, owner)).toBe(true);
  const newId = 0x100000000 + 99;
  expect(data.chatId).toBe(newId);
  expect(record.id).toBe(newId);
  expect(data.agentChatId).toBe('planning-a');
  expect(data.route).toEqual({ name: 'Completed route' });
  expect(existing).toEqual({
    id: 7,
    title: 'Existing trip',
    messages: [{ text: 'History', sender: 'bot' }],
  });
  expect(random).toHaveBeenCalledTimes(2);
  const [firstUrl, firstBody] = client.post.mock.calls[0],
    [secondUrl, secondBody] = client.post.mock.calls[1];
  expect(firstUrl).toContain('/chats/create/8');
  expect(firstBody.ChatData.chatId).toBe(8);
  expect(firstBody.ChatLog.id).toBe(8);
  expect(secondUrl).toContain('/chats/create/' + newId);
  expect(secondBody.ChatData.chatId).toBe(newId);
  expect(secondBody.ChatLog.id).toBe(newId);
  expect(secondBody.ChatData.agentChatId).toBe('planning-a');
  expect(Number.isSafeInteger(newId)).toBe(true);
  expect(newId).toBeLessThan(2 ** 48);
  expect(await ensureChatCreated(token, data, chats, owner)).toBe(true);
  expect(client.post).toHaveBeenCalledTimes(2);
  client.put.mockResolvedValueOnce({ status: 200 });
  expect(await updateUserData(token, data, chats, owner)).toBe(true);
  expect(client.put.mock.calls[0][0]).toContain('/chats/update/' + newId);
  expect(client.put.mock.calls[0][1].ChatLog.id).toBe(newId);
});
it('shares pending creation by planning identity while a collision changes the numeric ID', async () => {
  const data = planned(),
    record = log(),
    owner = {};
  let finish;
  randomIds([3, 100]);
  client.post.mockRejectedValueOnce(collision()).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const first = ensureChatCreated(token, data, [record], owner);
  await vi.waitFor(() => expect(client.post).toHaveBeenCalledTimes(2));
  const next = ensureChatCreated(token, data, [record], owner);
  expect(client.post).toHaveBeenCalledTimes(2);
  finish({ status: 201 });
  expect(await first).toBe(true);
  expect(await next).toBe(true);
  expect(await ensureChatCreated(token, data, [record], owner)).toBe(true);
  expect(client.post).toHaveBeenCalledTimes(2);
  // The abandoned original numeric ID was never marked ready for this lifecycle.
  client.post.mockResolvedValueOnce({ status: 201 });
  expect(await ensureChatCreated(token, { chatId: 8 }, [{ id: 8, messages: [] }], owner)).toBe(
    true
  );
  expect(client.post).toHaveBeenCalledTimes(3);
});
it('does not confuse two planning identities using the same initial numeric ID', async () => {
  const owner = {},
    first = planned(),
    second = { ...planned(), agentChatId: 'planning-b' };
  client.post
    .mockResolvedValueOnce({ status: 201 })
    .mockRejectedValueOnce(collision())
    .mockResolvedValueOnce({ status: 201 });
  randomIds([4, 101]);
  expect(await ensureChatCreated(token, first, [log()], owner)).toBe(true);
  const secondRecord = log();
  expect(await ensureChatCreated(token, second, [secondRecord], owner)).toBe(true);
  expect(first.chatId).toBe(8);
  expect(second.chatId).not.toBe(8);
  expect(secondRecord.id).toBe(second.chatId);
  expect(client.post).toHaveBeenCalledTimes(3);
});
it.each([
  { response: { status: 409, data: { detail: 'Another conflict' } } },
  { response: { status: 503, data: { detail: 'Storage unavailable' } } },
  new TypeError('Network outcome uncertain'),
])('does not renumber or automatically retry an unconfirmed failure', async (error) => {
  const data = planned(),
    record = log();
  client.post.mockRejectedValue(error);
  const random = randomIds();
  expect(await ensureChatCreated(token, data, [record], {})).toBe(false);
  expect(client.post).toHaveBeenCalledOnce();
  expect(random).not.toHaveBeenCalled();
  expect(data.chatId).toBe(8);
  expect(record.id).toBe(8);
});
it('bounds collision retries and clears pending failures for a later explicit save retry', async () => {
  const data = planned(),
    record = log(),
    owner = {};
  randomIds([5, 1], [6, 2]);
  client.post.mockRejectedValue(collision());
  expect(await ensureChatCreated(token, data, [record], owner)).toBe(false);
  expect(client.post).toHaveBeenCalledTimes(3);
  expect(record.id).toBe(data.chatId);
  client.post.mockResolvedValueOnce({ status: 201 });
  expect(await ensureChatCreated(token, data, [record], owner)).toBe(true);
  expect(client.post).toHaveBeenCalledTimes(4);
});
it('does not retry or publish readiness after the owner changes during a conflict', async () => {
  let reject;
  const data = planned(),
    record = log(),
    owner = {};
  client.post.mockImplementationOnce(
    () =>
      new Promise((_, fail) => {
        reject = fail;
      })
  );
  const pending = ensureChatCreated(token, data, [record], owner);
  await vi.waitFor(() => expect(client.post).toHaveBeenCalledOnce());
  fixtureSession('other');
  reject(collision());
  expect(await pending).toBe(false);
  expect(client.post).toHaveBeenCalledOnce();
  expect(data.chatId).toBe(8);
  client.post.mockResolvedValueOnce({ status: 201 });
  expect(await ensureChatCreated(getSession().accessToken, data, [record], owner)).toBe(true);
  expect(client.post).toHaveBeenCalledTimes(2);
});
it('does not mark a late successful response ready after sign out', async () => {
  let finish;
  const data = planned(),
    record = log(),
    owner = {};
  client.post.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const pending = ensureChatCreated(token, data, [record], owner);
  await vi.waitFor(() => expect(client.post).toHaveBeenCalledOnce());
  signOut();
  finish({ status: 201 });
  expect(await pending).toBe(false);
  token = fixtureSession().AccessToken;
  client.post.mockResolvedValueOnce({ status: 201 });
  expect(await ensureChatCreated(token, data, [record], owner)).toBe(true);
  expect(client.post).toHaveBeenCalledTimes(2);
});
it('retains direct legacy create behavior and fails closed when secure IDs cannot be allocated', async () => {
  const legacy = { chatId: 8 };
  client.post.mockRejectedValue(collision());
  const random = randomIds();
  expect(await createChat(token, legacy, log())).toBe(false);
  expect(client.post).toHaveBeenCalledOnce();
  expect(random).not.toHaveBeenCalled();
  client.post.mockClear();
  random.mockImplementation(() => {
    throw new Error('Random source unavailable');
  });
  const data = planned();
  expect(await ensureChatCreated(token, data, [log()], {})).toBe(false);
  expect(client.post).toHaveBeenCalledOnce();
  expect(data.chatId).toBe(8);
});

it('does not create duplicate local record IDs while aligning an already completed plan', async () => {
  const owner = {},
    data = planned(),
    record = log();
  randomIds([7, 202]);
  client.post.mockRejectedValueOnce(collision()).mockResolvedValueOnce({ status: 201 });
  expect(await ensureChatCreated(token, data, [record], owner)).toBe(true);
  const stale = planned(),
    oldRecord = log(),
    otherRecord = { id: data.chatId, title: 'Already aligned record', messages: [] };
  expect(await ensureChatCreated(token, stale, [oldRecord, otherRecord], owner)).toBe(false);
  expect(stale.chatId).toBe(8);
  expect(oldRecord.id).toBe(8);
  expect(otherRecord.id).toBe(data.chatId);
  expect(client.post).toHaveBeenCalledTimes(2);
});

it('does not allocate another ID or overwrite a newer saved version on a late same-planning create retry', async () => {
  const data = planned();
  const random = randomIds([1, 99]);
  client.post.mockRejectedValue({
    response: { status: 409, data: { detail: 'Trip already saved; reload before continuing' } },
  });
  expect(await ensureChatCreated(token, data, [log()], { chatdata: [] })).toBe(false);
  expect(data.saveConflict).toBe(true);
  expect(data.chatId).toBe(8);
  expect(client.post).toHaveBeenCalledTimes(1);
  expect(random).not.toHaveBeenCalled();
});
