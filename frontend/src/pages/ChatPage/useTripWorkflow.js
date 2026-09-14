/**
 * useTripWorkflow — thin agent-chat hook.
 *
 * The scripted step-machine is gone. The conversational agent (backend) now
 * gathers start/destination/stops/budget and calls tools itself; the frontend's
 * only job is:
 *   - send the user's free-text message to the agent
 *   - render the reply through the existing addMessage/loader path
 *   - when the agent's structured `actions` carry route/itinerary payloads,
 *     WRITE them into a ChatData snapshot so MapPage/ItineraryPage render.
 *
 * No step enum, no polling, no setInterval, no mutable class mutations. Messages
 * are read live from the `chats` context array by ChatPage.
 *
 * Agent action contract (frozen, verified live):
 *   action.type === 'route_updated'        → payload = { route, stops, cost }
 *   action.type === 'itinerary_updated'    → payload = { itinerary: [days...] }
 *   action.type === 'trip_profile_updated' → payload = { trip_profile: {...} }
 *     the per-chat TripProfile the agent fills in as it gathers the trip
 *     (start/destination/stops/budget); reflected into UI + persisted early.
 * The Route object carries `coordinates` = [[start_lat,start_lon], ...stops,
 * [end_lat,end_lon]]; startConfirmed/endConfirmed are derived from the first /
 * last coordinate so Map.jsx (which reads them) doesn't crash.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { updateUserData } from './DatabaseUtils';
import { sendAgentMessage } from './agentChat';

// ─── helpers ────────────────────────────────────────────────────────────────

const BOT = 'bot';
const USER = 'user';

/** Append a message to the named chat in `chats` state. */
export const addMessage = (chatId, setChats, text, sender) => {
  if (text === 'loading') {
    setChats((prev) =>
      prev.map((c) =>
        c.id === chatId ? { ...c, messages: [...c.messages, { type: 'loading-chat' }] } : c
      )
    );
    return;
  }
  const msg = { text: String(text), sender };
  setChats((prev) => {
    return prev.map((c) => {
      if (c.id !== chatId) return c;
      const last = c.messages[c.messages.length - 1];
      // Deduplicate consecutive identical messages
      if (last?.text === msg.text) return c;
      return { ...c, messages: [...c.messages, msg] };
    });
  });
};

/** Remove the loading bubble from a chat. */
export const removeLoader = (chatId, setChats) => {
  setChats((prev) =>
    prev.map((c) =>
      c.id === chatId ? { ...c, messages: c.messages.filter((m) => m.type !== 'loading-chat') } : c
    )
  );
};

/** Extract a city name from a full address string. */
export const extractCity = (addr) => {
  if (!addr) return null;
  const parts = addr.split(',').map((p) => p.trim());
  return parts.length >= 3 ? parts[1] : (parts[0] ?? null);
};

/** Rename a chat in the sidebar to "Trip to <endCity>". */
export const renameChatToRoute = (chatId, startConfirmed, endConfirmed, setChats) => {
  const endCity = extractCity(endConfirmed?.address);
  if (!endCity) return;
  setChats((prev) =>
    prev.map((c) => (c.id === chatId ? { ...c, title: `Trip to ${endCity}` } : c))
  );
};

/**
 * Derive a header-car progress value (1–5) from a ChatData-shaped object.
 * With the scripted machine gone there are only two meaningful states: a trip
 * with a route (done → 5) or one still being planned (1).
 */
export const deriveProgress = (chatData) => (chatData?.route ? 5 : 1);

/**
 * Derive a confirmed-location object ({latitude, longitude, address}) from a
 * Route coordinate pair `[lat, lon]`. Map.jsx crashes if startConfirmed /
 * endConfirmed are null, so we always populate them from the route geometry.
 * Address is unknown here (the agent validated it server-side) → ''.
 */
const confirmedFromCoord = (coord) => {
  if (!Array.isArray(coord) || coord.length < 2) return null;
  return { latitude: coord[0], longitude: coord[1], address: '' };
};

// The trip-profile fields we trace, in a stable display order.
const TRIP_PROFILE_FIELDS = [
  'start_address',
  'start_coords',
  'destination_address',
  'destination_coords',
  'num_stops',
  'budget',
  'start_date',
  'car',
];

/** Structural equality for trip-profile values (handles arrays/objects/scalars). */
const tripValuesEqual = (a, b) => {
  if (a === b) return true;
  if (a == null || b == null) return a == null && b == null;
  if (typeof a !== 'object' && typeof b !== 'object') return a === b;
  return JSON.stringify(a) === JSON.stringify(b);
};

/**
 * Diff two trip-profile objects and log per-field ADDED / REMOVED / CHANGED at
 * the turn level. Pure except for the console output; exported for testing.
 *
 * @param {object|null} prev  the trip profile before this turn (may be {}/null)
 * @param {object|null} next  the trip profile from the trip_profile_updated action
 * @returns {Array<{field:string, kind:string, from:*, to:*}>} the changes logged
 */
export const logTripProfileChanges = (prev, next) => {
  const before = prev && typeof prev === 'object' ? prev : {};
  const after = next && typeof next === 'object' ? next : {};
  const changes = [];

  for (const field of TRIP_PROFILE_FIELDS) {
    const had = before[field] !== undefined && before[field] !== null;
    const has = after[field] !== undefined && after[field] !== null;

    if (!had && has) {
      changes.push({ field, kind: 'ADDED', from: undefined, to: after[field] });
    } else if (had && !has) {
      changes.push({ field, kind: 'REMOVED', from: before[field], to: undefined });
    } else if (had && has && !tripValuesEqual(before[field], after[field])) {
      changes.push({ field, kind: 'CHANGED', from: before[field], to: after[field] });
    }
  }

  // Emit at the default Console level (console.log) — not console.debug, which
  // Chrome/Edge hide behind the "Verbose" filter — so the trip-profile trace is
  // visible without changing DevTools log-level settings.
  if (changes.length === 0) {
    console.log('[TripProfile] update applied — no field changes');
  } else {
    for (const c of changes) {
      if (c.kind === 'ADDED') {
        console.log('[TripProfile] + %s = %o', c.field, c.to);
      } else if (c.kind === 'REMOVED') {
        console.log('[TripProfile] - %s (was %o)', c.field, c.from);
      } else {
        console.log('[TripProfile] ~ %s: %o → %o', c.field, c.from, c.to);
      }
    }
  }
  // Always log the FULL current state so you can watch the data object fill in.
  console.log('[TripProfile] current state:', after);
  return changes;
};

/**
 * Turn-level trace of the agent's trip-data tooling. Logs which tools ran, prints
 * any tool errors the backend surfaced (`toolErrors`), and flags a likely
 * VALIDATION FAILURE when the agent attempted `update_trip_profile` but no
 * `trip_profile_updated` action came back (a failed update is fed back to the
 * model, so it never appears in `actions`). Exported for testing.
 *
 * @param {string[]} toolsUsed   response.toolsUsed
 * @param {Array}    actions      response.actions
 * @param {Array}    [toolErrors] response.toolErrors — [{ name, error }]
 * @returns {boolean} true when a probable trip-profile validation failure was detected
 */
export const logTripToolActivity = (toolsUsed, actions, toolErrors) => {
  const tools = Array.isArray(toolsUsed) ? toolsUsed : [];
  const acts = Array.isArray(actions) ? actions : [];
  const errors = Array.isArray(toolErrors) ? toolErrors : [];
  if (tools.length > 0) {
    console.log('[TripProfile] tools this turn: %s', tools.join(', '));
  }
  // Print the exact backend error for every failed tool (e.g. the validation
  // message from a rejected update_trip_profile) so debugging stays in-browser.
  for (const e of errors) {
    if (e?.name && e?.error) {
      console.warn('[TripProfile] tool %s failed: %s', e.name, e.error);
    }
  }
  const attemptedUpdate = tools.filter((t) => t === 'update_trip_profile').length;
  const appliedUpdate = acts.filter((a) => a?.type === 'trip_profile_updated').length;
  if (attemptedUpdate > appliedUpdate) {
    const detail = errors
      .filter((e) => e?.name === 'update_trip_profile' && e?.error)
      .map((e) => e.error)
      .join(' | ');
    console.warn(
      '[TripProfile] VALIDATION FAILURE: update_trip_profile ran %d time(s) but only %d ' +
        'applied — the agent tried to store a value that failed validation.%s',
      attemptedUpdate,
      appliedUpdate,
      detail ? ` Detail: ${detail}` : ' (no error detail returned; check the backend agent log.)'
    );
    return true;
  }
  return false;
};

// ─── hook ────────────────────────────────────────────────────────────────────

/**
 * @param {object}   opts
 * @param {number}   opts.chatId        – live chat ID (may change after DB fetch)
 * @param {function} opts.setChats      – context setter
 * @param {function} opts.setCurrentStep – header car progress setter (kept for compat)
 * @param {object}   opts.savedData     – ChatData loaded from DB (for resuming)
 * @param {object}   opts.chatsRef      – ref to live chats array
 * @param {string}   opts.accessToken
 * @param {object}   opts.ChatLogsData  – ChatLogs instance
 * @param {string}   [opts.agentChatId] – globally-unique agent conversation key
 *   (a UUID). Sent to the backend as the agent `chatId` so per-chat memory never
 *   collides with a reused integer chat id. Falls back to the integer chatId.
 * @param {function} [opts.onChatReady] – called with (chatId, title) once a route lands
 */
export function useTripWorkflow({
  chatId,
  agentChatId,
  setChats,
  setCurrentStep,
  savedData,
  chatsRef,
  accessToken,
  ChatLogsData,
  onChatReady,
}) {
  // Agent-driven trip data — plain React state.
  const [route, setRoute] = useState(savedData?.route ?? null);
  const [itinerary, setItinerary] = useState(savedData?.itinerary ?? null);
  const [startConfirmed, setStartConfirmed] = useState(savedData?.startConfirmed ?? null);
  const [endConfirmed, setEndConfirmed] = useState(savedData?.endConfirmed ?? null);
  const [stops, setStops] = useState(savedData?.stops ?? 1);
  const [budget, setBudget] = useState(savedData?.budget ?? null);
  // Hotel budget is only carried through from a resumed trip; the agent reports
  // total cost via route payloads, so this value is never mutated here.
  const hotelBudget = savedData?.hotelBudget ?? 0;

  // Prevents concurrent submit calls (StrictMode double-invoke / rapid clicks).
  const submitInFlightRef = useRef(false);
  // Drives the ChatInput disabled state while a turn is in flight, so the send
  // button can't be used until the agent finishes and the user should type again.
  const [isLoading, setIsLoading] = useState(false);

  // Last trip-profile snapshot the agent reported, so we can diff each turn's
  // trip_profile_updated action and log field-level ADDED/REMOVED/CHANGED.
  const tripProfileRef = useRef(savedData?.tripProfile ?? {});

  // Keep chatId in a ref so callbacks always use the live value.
  const chatIdRef = useRef(chatId);
  useEffect(() => {
    chatIdRef.current = chatId;
  }, [chatId]);

  // The globally-unique agent conversation key sent to the backend. Falls back
  // to the integer chatId if none was provided (keeps the hook usable standalone
  // / in tests). Kept in a ref so callbacks read the live value.
  const agentChatIdRef = useRef(agentChatId ?? String(chatId));
  useEffect(() => {
    agentChatIdRef.current = agentChatId ?? String(chatId);
  }, [agentChatId, chatId]);

  // Header car position — a route means the trip is planned (5), else 1.
  useEffect(() => {
    setCurrentStep(deriveProgress({ route }));
  }, [route, setCurrentStep]);

  // ── Message shorthands ───────────────────────────────────────────────────
  const bot = useCallback((text) => addMessage(chatIdRef.current, setChats, text, BOT), [setChats]);
  const loading = useCallback(
    () => addMessage(chatIdRef.current, setChats, 'loading', BOT),
    [setChats]
  );
  const noLoader = useCallback(() => removeLoader(chatIdRef.current, setChats), [setChats]);

  // ── Build a ChatData-shaped snapshot for DB persistence ──────────────────
  // Same 24 positional fields the ChatData constructor / DatabaseUtils expect.
  // Populated from agent-derived state; legacy UI-flag fields stay false/empty.
  const buildSnapshot = useCallback(
    (overrides = {}) => {
      const r = overrides.route !== undefined ? overrides.route : route;
      const start =
        overrides.startConfirmed !== undefined ? overrides.startConfirmed : startConfirmed;
      const end = overrides.endConfirmed !== undefined ? overrides.endConfirmed : endConfirmed;
      const stopCount = overrides.stops !== undefined ? overrides.stops : stops;
      const b = overrides.budget !== undefined ? overrides.budget : budget;
      return {
        chatId: chatIdRef.current,
        action: null,
        locationType: 'start',
        startCoords: start ? [start.latitude, start.longitude] : null,
        startAddress: new Array(4).fill(''),
        endCoords: end ? [end.latitude, end.longitude] : null,
        endAddress: new Array(4).fill(''),
        stops: stopCount,
        showInputBar: false,
        showStopSlider: false,
        showBudgetSlider: false,
        showAddressInput: false,
        workflowStarted: true,
        startConfirmed: start,
        endConfirmed: end,
        initial: null,
        route: r,
        itinerary: overrides.itinerary !== undefined ? overrides.itinerary : itinerary,
        loading: false,
        hotelBudget: overrides.hotelBudget !== undefined ? overrides.hotelBudget : hotelBudget,
        carBudget: 0,
        carDetails: new Array(3).fill(''),
        budget: b,
        isComplete: !!r,
      };
    },
    [route, startConfirmed, endConfirmed, stops, budget, itinerary, hotelBudget]
  );

  // ── Persist a snapshot everywhere Map/Itinerary read from ────────────────
  // Writes into ChatLogsData.chatdata[idx] + chatsRef and the backend, so
  // ChatLogsData.getChatDataById(currentId) reflects the new route/itinerary.
  const persistSnapshot = useCallback(
    async (snap) => {
      const idx = ChatLogsData.chatdata.findIndex((c) => c.chatId === snap.chatId);
      if (idx !== -1) ChatLogsData.chatdata[idx] = snap;
      else ChatLogsData.chatdata.push(snap);
      await updateUserData(accessToken, snap, chatsRef.current);
    },
    [ChatLogsData, accessToken, chatsRef]
  );

  // ── Apply structured agent actions ────────────────────────────────────────
  // route_updated  → payload.route drives route + derived start/end confirmed
  // itinerary_updated → payload.itinerary drives the itinerary
  // Then persist a ChatData snapshot so Map/Itinerary/DB see it.
  const applyAgentActions = useCallback(
    async (actions) => {
      if (!Array.isArray(actions) || actions.length === 0) return;

      const overrides = {};
      let sawRoute = false;

      for (const action of actions) {
        if (!action || typeof action !== 'object') continue;

        if (action.type === 'route_updated' && action.payload?.route) {
          const newRoute = action.payload.route;
          setRoute(newRoute);
          overrides.route = newRoute;
          sawRoute = true;

          const coords = newRoute.coordinates;
          if (Array.isArray(coords) && coords.length >= 2) {
            const start = confirmedFromCoord(coords[0]);
            const end = confirmedFromCoord(coords[coords.length - 1]);
            if (start) {
              setStartConfirmed(start);
              overrides.startConfirmed = start;
            }
            if (end) {
              setEndConfirmed(end);
              overrides.endConfirmed = end;
            }
          }

          if (typeof action.payload.cost === 'number') {
            setBudget(action.payload.cost);
            overrides.budget = action.payload.cost;
          }
          if (Array.isArray(action.payload.stops)) {
            const n = action.payload.stops.length;
            setStops(n);
            overrides.stops = n;
          } else if (typeof action.payload.stops === 'number') {
            setStops(action.payload.stops);
            overrides.stops = action.payload.stops;
          }
        } else if (
          action.type === 'itinerary_updated' &&
          Array.isArray(action.payload?.itinerary)
        ) {
          setItinerary(action.payload.itinerary);
          overrides.itinerary = action.payload.itinerary;
        } else if (
          action.type === 'trip_profile_updated' &&
          action.payload?.trip_profile &&
          typeof action.payload.trip_profile === 'object'
        ) {
          // The agent gathered a trip detail (start/destination/stops/budget)
          // into this chat's TripProfile. Reflect the fields the UI tracks so
          // Map/derived state and the persisted snapshot stay in sync — even
          // before a full route exists.
          const tp = action.payload.trip_profile;
          // Turn-level trace: what was added / removed / changed this turn.
          logTripProfileChanges(tripProfileRef.current, tp);
          tripProfileRef.current = tp;
          if (Array.isArray(tp.start_coords) && tp.start_coords.length >= 2) {
            const start = confirmedFromCoord(tp.start_coords);
            if (start) {
              if (tp.start_address) start.address = tp.start_address;
              setStartConfirmed(start);
              overrides.startConfirmed = start;
            }
          }
          if (Array.isArray(tp.destination_coords) && tp.destination_coords.length >= 2) {
            const end = confirmedFromCoord(tp.destination_coords);
            if (end) {
              if (tp.destination_address) end.address = tp.destination_address;
              setEndConfirmed(end);
              overrides.endConfirmed = end;
            }
          }
          if (typeof tp.num_stops === 'number') {
            setStops(tp.num_stops);
            overrides.stops = tp.num_stops;
          }
          if (typeof tp.budget === 'number') {
            setBudget(tp.budget);
            overrides.budget = tp.budget;
          }
        }
      }

      if (Object.keys(overrides).length === 0) return;

      const snap = buildSnapshot(overrides);

      // Title the chat once a route first lands (agent gathered the destination).
      if (sawRoute && onChatReady) {
        const endCity = extractCity(snap.endConfirmed?.address);
        onChatReady(chatIdRef.current, endCity ? `Trip to ${endCity}` : null);
      }

      await persistSnapshot(snap);
    },
    [buildSnapshot, persistSnapshot, onChatReady]
  );

  // ── Public: submit user input (agent chat only) ───────────────────────────
  const submit = useCallback(
    async (action, payload) => {
      if (action !== 'chat_message') return;

      // Guard against StrictMode double-invoke or rapid double-clicks.
      if (submitInFlightRef.current) return;
      submitInFlightRef.current = true;
      setIsLoading(true);

      const id = chatIdRef.current;
      try {
        const text = typeof payload === 'string' ? payload.trim() : '';
        if (!text) return;

        addMessage(id, setChats, text, USER);
        loading();
        const response = await sendAgentMessage({
          accessToken,
          // Use the globally-unique agent conversation key (a UUID), NOT the
          // reused integer chat id, so per-chat memory never collides.
          chatId: agentChatIdRef.current,
          message: text,
          clientContext: { hasRoute: !!route, stops, hotelBudget },
        });
        noLoader();

        if (response && typeof response.reply === 'string') {
          bot(response.reply);
          // Turn-level trace: tools run, any tool errors, and a flag for a probable
          // trip-profile validation failure (attempted update with no applied action).
          logTripToolActivity(response.toolsUsed, response.actions, response.toolErrors);
          await applyAgentActions(response.actions);
        } else {
          // The turn produced NO reply (network / 503 / other). This is not an
          // agent-recoverable tool error — those are fed back within the turn and
          // come back as a normal reply. A 503 is transient (provider/gateway),
          // so nudge a retry; anything else is a generic failure.
          const status = response?.status ?? null;
          bot(
            status === 503
              ? "I'm having trouble reaching my planning service right now. Give it another try in a moment."
              : 'Something went wrong on my end. Please try sending that again.'
          );
        }
      } finally {
        submitInFlightRef.current = false;
        setIsLoading(false);
      }
    },
    [accessToken, route, stops, hotelBudget, bot, loading, noLoader, setChats, applyAgentActions]
  );

  return {
    submit,
    route,
    itinerary,
    // true while a turn is in flight — drives the ChatInput disabled state.
    isLoading,
    // kept for potential compatibility; the persistent ChatInput is the only input now.
    inputMode: 'none',
  };
}
