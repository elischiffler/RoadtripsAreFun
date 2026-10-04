import { createProgressLogger } from './agentProgress';
import { updateTripProgress } from './tripProgressState';
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
import { getRoutingAlgorithm } from './getRoute';

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
  'start_timezone',
  'destination_address',
  'destination_coords',
  'num_stops',
  'budget',
  'start_date',
  'departure_time',
  'car',
  'car_status',
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
 * Turn-level trace of the agent's trip-data tooling. Logs every turn, including
 * turns with no tools, plus backend tool errors and field-specific clarifications.
 *
 * @param {string[]} toolsUsed   response.toolsUsed
 * @param {Array}    [toolErrors] response.toolErrors — [{ name, error }]
 * @param {object}   [validationIssues] response.validationIssues — field to clarification
 * @param {string[]} [extractedFields] response.extractedFields — fields identified in this turn
 * @returns {boolean} true when the backend reported a validation issue or tool error
 */
export const logTripToolActivity = (toolsUsed, toolErrors, validationIssues, extractedFields) => {
  const tools = Array.isArray(toolsUsed) ? toolsUsed : [];
  const errors = Array.isArray(toolErrors) ? toolErrors : [];
  console.log('[TripProfile] tools this turn: %s', tools.length ? tools.join(', ') : 'none');
  console.log(
    '[TripProfile] extracted fields this turn: %s',
    Array.isArray(extractedFields) && extractedFields.length ? extractedFields.join(', ') : 'none'
  );
  // Print backend validation errors so debugging stays in-browser.
  for (const e of errors) {
    if (e?.name && e?.error) {
      console.warn('[TripProfile] tool %s failed: %s', e.name, e.error);
    }
  }
  const issues = validationIssues && typeof validationIssues === 'object' ? validationIssues : {};
  for (const [field, detail] of Object.entries(issues)) {
    console.warn('[TripProfile] %s needs clarification: %s', field, detail);
  }
  return errors.length > 0 || Object.keys(issues).length > 0;
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
  const [processProgress, setProcessProgress] = useState(null);

  // Last trip-profile snapshot the agent reported, so we can diff each turn's
  // trip_profile_updated action and log field-level ADDED/REMOVED/CHANGED.
  const tripProfileRef = useRef(savedData?.tripProfile ?? {});
  const [tripProfile, setTripProfile] = useState(savedData?.tripProfile ?? {});

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
      const plannedItinerary = overrides.itinerary !== undefined ? overrides.itinerary : itinerary;
      return {
        chatId: chatIdRef.current,
        agentChatId: agentChatIdRef.current,
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
        itinerary: plannedItinerary,
        loading: false,
        hotelBudget: overrides.hotelBudget !== undefined ? overrides.hotelBudget : hotelBudget,
        carBudget: 0,
        carDetails: new Array(3).fill(''),
        budget: b,
        isComplete: !!r && Array.isArray(plannedItinerary) && plannedItinerary.length > 0,
        tripProfile: tripProfileRef.current,
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
      const saved = await updateUserData(accessToken, snap, chatsRef.current);
      if (!saved) bot("I couldn't save this trip. Please try again before leaving this page.");
    },
    [ChatLogsData, accessToken, chatsRef, bot]
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
          if (Array.isArray(newRoute.warnings)) {
            newRoute.warnings.forEach((warning) => bot(warning));
          }
          setRoute(newRoute);
          overrides.route = newRoute;
          sawRoute = true;
          // A newly planned route invalidates any itinerary from an older route.
          // A following itinerary_updated action in this response replaces it.
          setItinerary(null);
          overrides.itinerary = null;

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
          const previous = tripProfileRef.current;
          if (
            ['start_coords', 'destination_coords'].some(
              (field) => tp[field] && JSON.stringify(tp[field]) !== JSON.stringify(previous[field])
            )
          ) {
            setRoute(null);
            setItinerary(null);
            overrides.route = null;
            overrides.itinerary = null;
          }
          tripProfileRef.current = tp;
          overrides.tripProfile = tp;
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
    [buildSnapshot, persistSnapshot, onChatReady, bot]
  );

  // ── Public: submit user input (agent chat only) ───────────────────────────
  const submit = useCallback(
    async (action, payload) => {
      if (action !== 'chat_message' && action !== 'location_confirmation') return;

      // Guard against StrictMode double-invoke or rapid double-clicks.
      if (submitInFlightRef.current) return;
      submitInFlightRef.current = true;
      setIsLoading(true);

      const id = chatIdRef.current;
      try {
        const confirmation = action === 'location_confirmation' ? payload : null;
        const text = confirmation
          ? `Use ${confirmation.address}`
          : typeof payload === 'string'
            ? payload.trim()
            : '';
        if (!text) return;

        addMessage(id, setChats, text, USER);
        loading();
        setProcessProgress({ startedAt: Date.now(), entries: [] });
        const logProgress = import.meta.env.DEV ? createProgressLogger() : null;
        const response = await sendAgentMessage({
          accessToken,
          onProgress: (event) => {
            logProgress?.(event);
            setProcessProgress((previous) => updateTripProgress(previous, event));
          },
          // Use the globally-unique agent conversation key (a UUID), NOT the
          // reused integer chat id, so per-chat memory never collides.
          chatId: agentChatIdRef.current,
          message: text,
          ...(confirmation
            ? {
                locationConfirmation: {
                  field: confirmation.field,
                  candidateId: confirmation.candidateId,
                },
              }
            : {}),
          clientContext: {
            hasRoute: !!route,
            stops,
            hotelBudget,
            ...(getRoutingAlgorithm() ? { algorithm: getRoutingAlgorithm() } : {}),
          },
        });
        noLoader();

        if (response && typeof response.reply === 'string') {
          bot(response.reply);
          if (response.tripProfile) setTripProfile(response.tripProfile);
          // Trace tool activity and the backend's authoritative profile on every turn.
          logTripToolActivity(
            response.toolsUsed,
            response.toolErrors,
            response.validationIssues,
            response.extractedFields
          );
          await applyAgentActions(response.actions);
          if (
            response.tripProfile &&
            !response.actions?.some((action) => action?.type === 'trip_profile_updated')
          ) {
            logTripProfileChanges(tripProfileRef.current, response.tripProfile);
            tripProfileRef.current = response.tripProfile;
          }
          if (response.tripProfile && !response.actions?.length)
            await persistSnapshot(buildSnapshot());
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
        noLoader();
        submitInFlightRef.current = false;
        setIsLoading(false);
        setProcessProgress(null);
      }
    },
    [
      accessToken,
      route,
      stops,
      hotelBudget,
      bot,
      loading,
      noLoader,
      setChats,
      applyAgentActions,
      persistSnapshot,
      buildSnapshot,
    ]
  );

  return {
    submit,
    route,
    itinerary,
    // true while a turn is in flight — drives the ChatInput disabled state.
    isLoading,
    processProgress,
    pendingLocations: tripProfile.pending_locations ?? {},
    // kept for potential compatibility; the persistent ChatInput is the only input now.
    inputMode: 'none',
  };
}
