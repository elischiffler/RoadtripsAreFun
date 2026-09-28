import { beforeEach, describe, expect, it } from 'vitest';
import {
  chooseRestoredChatId,
  forgetAgentChatId,
  getOrCreateAgentChatId,
} from '../pages/ChatPage/chatSession';

beforeEach(() => sessionStorage.clear());

describe('saved chat reload', () => {
  it('reselects saved chat 1 instead of the new empty scaffold', () => {
    expect(chooseRestoredChatId(1, [{ id: 1 }, { id: 3 }], 4)).toBe(1);
    expect(chooseRestoredChatId(2, [{ id: 1 }, { id: 3 }], 4)).toBe(4);
  });

  it('keeps one agent conversation ID across reload and later snapshots', () => {
    const cache = new Map();
    const chatData = { chatId: 1 };
    const generated = getOrCreateAgentChatId(1, chatData, cache);
    expect(chatData.agentChatId).toBe(generated);
    expect(getOrCreateAgentChatId(1, { chatId: 1 }, new Map())).toBe(generated);
    expect(getOrCreateAgentChatId(1, { chatId: 1, agentChatId: generated }, new Map())).toBe(
      generated
    );

    forgetAgentChatId(1, cache);
    expect(sessionStorage.getItem('roadtrips.agentChatId.1')).toBeNull();
  });

  it('prefers the database ID over a stale local session mapping', () => {
    sessionStorage.setItem('roadtrips.agentChatId.1', 'stale-id');
    const data = { chatId: 1, agentChatId: 'saved-id' };
    expect(getOrCreateAgentChatId(1, data, new Map())).toBe('saved-id');
    expect(sessionStorage.getItem('roadtrips.agentChatId.1')).toBe('saved-id');
  });
});
