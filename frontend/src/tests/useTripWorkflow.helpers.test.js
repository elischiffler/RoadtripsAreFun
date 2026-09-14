/**
 * useTripWorkflow — pure helper unit tests
 *
 * These test the exported helper functions (addMessage, removeLoader,
 * extractCity, renameChatToRoute, deriveProgress) in complete isolation
 * — no React rendering required.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  addMessage,
  removeLoader,
  extractCity,
  renameChatToRoute,
  deriveProgress,
  logTripProfileChanges,
  logTripToolActivity,
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

// ─── deriveProgress ──────────────────────────────────────────────────────────

describe('deriveProgress', () => {
  it('returns 5 when the chat has a route', () => {
    expect(deriveProgress({ route: { duration: 100 } })).toBe(5);
  });

  it('returns 1 when there is no route', () => {
    expect(deriveProgress({ route: null })).toBe(1);
    expect(deriveProgress({})).toBe(1);
    expect(deriveProgress(null)).toBe(1);
  });
});

// ─── logTripProfileChanges ───────────────────────────────────────────────────

describe('logTripProfileChanges', () => {
  beforeEach(() => {
    // Trace output goes to console.log (default level, not the hidden Verbose
    // console.debug) so it's visible in DevTools without changing log-level filters.
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('reports ADDED fields when going from empty to populated', () => {
    const changes = logTripProfileChanges(
      {},
      { start_address: '482 Luneta Dr', start_coords: [35.28, -120.66] }
    );
    expect(changes).toEqual([
      { field: 'start_address', kind: 'ADDED', from: undefined, to: '482 Luneta Dr' },
      { field: 'start_coords', kind: 'ADDED', from: undefined, to: [35.28, -120.66] },
    ]);
  });

  it('reports a CHANGED field when a scalar value differs', () => {
    const changes = logTripProfileChanges({ num_stops: 2 }, { num_stops: 4 });
    expect(changes).toEqual([{ field: 'num_stops', kind: 'CHANGED', from: 2, to: 4 }]);
  });

  it('reports a CHANGED field when a coordinate array differs', () => {
    const changes = logTripProfileChanges(
      { start_coords: [35.28, -120.66] },
      { start_coords: [39.74, -104.99] }
    );
    expect(changes).toEqual([
      { field: 'start_coords', kind: 'CHANGED', from: [35.28, -120.66], to: [39.74, -104.99] },
    ]);
  });

  it('reports a REMOVED field when a value goes away', () => {
    const changes = logTripProfileChanges({ budget: 200 }, {});
    expect(changes).toEqual([{ field: 'budget', kind: 'REMOVED', from: 200, to: undefined }]);
  });

  it('reports no changes when nothing differs (deep-equal arrays)', () => {
    const changes = logTripProfileChanges(
      { start_coords: [1, 2], num_stops: 3 },
      { start_coords: [1, 2], num_stops: 3 }
    );
    expect(changes).toEqual([]);
  });

  it('tolerates null/undefined prev and logs everything as ADDED', () => {
    const changes = logTripProfileChanges(null, { budget: 150 });
    expect(changes).toEqual([{ field: 'budget', kind: 'ADDED', from: undefined, to: 150 }]);
  });

  it('always logs the full current state of the trip profile', () => {
    const next = { start_address: '482 Luneta Dr', num_stops: 3 };
    logTripProfileChanges({ start_address: '482 Luneta Dr' }, next);
    // The complete current object is logged (so you can watch it fill in),
    // regardless of what changed.
    const loggedState = console.log.mock.calls.some(
      (args) => args[0] === '[TripProfile] current state:' && args[1] === next
    );
    expect(loggedState).toBe(true);
  });

  it('logs the full current state even when nothing changed', () => {
    const same = { num_stops: 3 };
    logTripProfileChanges(same, same);
    const loggedState = console.log.mock.calls.some(
      (args) => args[0] === '[TripProfile] current state:' && args[1] === same
    );
    expect(loggedState).toBe(true);
  });
});

// ─── logTripToolActivity ─────────────────────────────────────────────────────

describe('logTripToolActivity', () => {
  beforeEach(() => {
    vi.spyOn(console, 'debug').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('flags a validation failure when update ran but no action applied', () => {
    const failed = logTripToolActivity(
      ['validate_location', 'update_trip_profile'],
      [] // no trip_profile_updated action came back
    );
    expect(failed).toBe(true);
    expect(console.warn).toHaveBeenCalled();
  });

  it('includes the backend error detail in the validation-failure warning', () => {
    logTripToolActivity(
      ['update_trip_profile'],
      [],
      [{ name: 'update_trip_profile', error: 'num_stops must be between 1 and 10' }]
    );
    // The warning carries the actual backend validation message.
    const warned = console.warn.mock.calls.some((args) =>
      args.some((a) => typeof a === 'string' && a.includes('num_stops must be between 1 and 10'))
    );
    expect(warned).toBe(true);
  });

  it('logs each tool error the backend surfaced', () => {
    logTripToolActivity(
      ['validate_location', 'update_trip_profile'],
      [{ type: 'trip_profile_updated', payload: {} }],
      [{ name: 'validate_location', error: 'Location not found' }]
    );
    const warned = console.warn.mock.calls.some((args) =>
      args.some((a) => typeof a === 'string' && a.includes('Location not found'))
    );
    expect(warned).toBe(true);
  });

  it('does not flag when the update applied (action present)', () => {
    const failed = logTripToolActivity(
      ['update_trip_profile'],
      [{ type: 'trip_profile_updated', payload: { trip_profile: { num_stops: 3 } } }]
    );
    expect(failed).toBe(false);
    expect(console.warn).not.toHaveBeenCalled();
  });

  it('does not flag when update_trip_profile was never attempted', () => {
    const failed = logTripToolActivity(['validate_location'], []);
    expect(failed).toBe(false);
  });

  it('tolerates missing/undefined inputs', () => {
    expect(logTripToolActivity(undefined, undefined, undefined)).toBe(false);
  });
});
