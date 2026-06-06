/**
 * useTripWorkflow — pure helper unit tests
 *
 * These test the exported helper functions (addMessage, removeLoader,
 * extractCity, renameChatToRoute, stepToProgress) in complete isolation
 * — no React rendering required.
 */
import { describe, it, expect, vi } from 'vitest';
import {
  addMessage,
  removeLoader,
  extractCity,
  renameChatToRoute,
  stepToProgress,
} from '../pages/ChatPage/useTripWorkflow';

// ─── addMessage ──────────────────────────────────────────────────────────────

describe('addMessage', () => {
  it('appends a text message to the matching chat', () => {
    const setChats = vi.fn();
    addMessage(1, setChats, 'Hello!', 'bot');

    // Extract the updater fn passed to setChats
    const updater = setChats.mock.calls[0][0];
    const prev = [{ id: 1, messages: [] }];
    const next = updater(prev);

    expect(next[0].messages).toHaveLength(1);
    expect(next[0].messages[0]).toEqual({ text: 'Hello!', sender: 'bot' });
  });

  it('inserts a loading bubble when text is "loading"', () => {
    const setChats = vi.fn();
    addMessage(1, setChats, 'loading', 'bot');

    const updater = setChats.mock.calls[0][0];
    const prev = [{ id: 1, messages: [] }];
    const next = updater(prev);

    expect(next[0].messages[0]).toEqual({ type: 'loading-chat' });
  });

  it('deduplicates consecutive identical messages', () => {
    const setChats = vi.fn();
    const existingMsg = { text: 'Where are you starting from?', sender: 'bot' };
    addMessage(1, setChats, 'Where are you starting from?', 'bot');

    const updater = setChats.mock.calls[0][0];
    const prev = [{ id: 1, messages: [existingMsg] }];
    const next = updater(prev);

    // Should NOT add a second copy
    expect(next[0].messages).toHaveLength(1);
  });

  it('does not touch other chats', () => {
    const setChats = vi.fn();
    addMessage(2, setChats, 'Hi', 'user');

    const updater = setChats.mock.calls[0][0];
    const prev = [
      { id: 1, messages: [] },
      { id: 2, messages: [] },
    ];
    const next = updater(prev);

    expect(next[0].messages).toHaveLength(0); // chat 1 untouched
    expect(next[1].messages).toHaveLength(1);
  });
});

// ─── removeLoader ────────────────────────────────────────────────────────────

describe('removeLoader', () => {
  it('removes loading bubbles from the matching chat', () => {
    const setChats = vi.fn();
    removeLoader(1, setChats);

    const updater = setChats.mock.calls[0][0];
    const prev = [{ id: 1, messages: [{ type: 'loading-chat' }, { text: 'Hi', sender: 'bot' }] }];
    const next = updater(prev);

    expect(next[0].messages).toEqual([{ text: 'Hi', sender: 'bot' }]);
  });

  it('leaves a chat with no loader unchanged', () => {
    const setChats = vi.fn();
    removeLoader(1, setChats);

    const updater = setChats.mock.calls[0][0];
    const prev = [{ id: 1, messages: [{ text: 'Hello', sender: 'bot' }] }];
    const next = updater(prev);

    expect(next[0].messages).toHaveLength(1);
  });
});

// ─── extractCity ─────────────────────────────────────────────────────────────

describe('extractCity', () => {
  it('returns city (index 1) from a comma-separated address', () => {
    expect(extractCity('123 Main St, Springfield, IL 62701, USA')).toBe('Springfield');
  });

  it('returns the first part when the address has fewer than 3 segments', () => {
    expect(extractCity('Springfield, IL')).toBe('Springfield');
  });

  it('returns null for a null / undefined input', () => {
    expect(extractCity(null)).toBeNull();
    expect(extractCity(undefined)).toBeNull();
  });

  it('returns null for an empty string', () => {
    expect(extractCity('')).toBeNull();
  });
});

// ─── renameChatToRoute ───────────────────────────────────────────────────────

describe('renameChatToRoute', () => {
  it('renames the chat to "Trip to <endCity>"', () => {
    const setChats = vi.fn();
    const endConfirmed = { address: '123 Main St, Denver, CO 80203, USA' };

    renameChatToRoute(1, null, endConfirmed, setChats);

    const updater = setChats.mock.calls[0][0];
    const prev = [{ id: 1, title: 'New Trip' }];
    const next = updater(prev);

    expect(next[0].title).toBe('Trip to Denver');
  });

  it('does nothing when endConfirmed has no extractable city', () => {
    const setChats = vi.fn();
    renameChatToRoute(1, null, { address: null }, setChats);
    expect(setChats).not.toHaveBeenCalled();
  });
});

// ─── stepToProgress ──────────────────────────────────────────────────────────

describe('stepToProgress', () => {
  it('returns 1 for idle and start_input', () => {
    expect(stepToProgress('idle')).toBe(1);
    expect(stepToProgress('start_input')).toBe(1);
  });

  it('returns 2 for start_validating / end_input', () => {
    expect(stepToProgress('start_validating')).toBe(2);
    expect(stepToProgress('end_input')).toBe(2);
  });

  it('returns 3 for end_validating / fetching_initial / stops_input', () => {
    expect(stepToProgress('end_validating')).toBe(3);
    expect(stepToProgress('fetching_initial')).toBe(3);
    expect(stepToProgress('stops_input')).toBe(3);
  });

  it('returns 4 for fetching_budget / budget_input / car_input', () => {
    expect(stepToProgress('fetching_budget')).toBe(4);
    expect(stepToProgress('budget_input')).toBe(4);
    expect(stepToProgress('car_input')).toBe(4);
  });

  it('returns 5 for generating_route and done', () => {
    expect(stepToProgress('generating_route')).toBe(5);
    expect(stepToProgress('done')).toBe(5);
  });

  it('returns 1 for unknown steps', () => {
    expect(stepToProgress('some_unknown_step')).toBe(1);
  });
});
