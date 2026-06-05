/**
 * useTripWorkflow — state-machine-based trip planning workflow.
 *
 * Replaces the polling-based startWorkFlow.jsx with a React-idiomatic approach:
 *   - `step` is a string enum stored in React state
 *   - Each step change triggers a useEffect that does one unit of work
 *   - User input calls `submit(payload)` which validates and advances the step
 *   - No setInterval, no mutable class mutations, no stale closures
 *
 * Step order:
 *   idle → start_input → start_validating → end_input → end_validating →
 *   fetching_initial → stops_input → fetching_budget → budget_input →
 *   car_input → prefetching_route → generating_route → done | error
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { getInitialRoute, getFinalRoute } from './getRoute';
import { calcHotelBudget, calcGasBudget } from './CalcBudget';
import { generateItinerary } from '../ItineraryPage/generateItinerary';
import { updateUserData, createChat } from './DatabaseUtils';

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

/** Call the backend to geocode / reverse-geocode a location. */
const validateLocationApi = async (input, isCoordinate) => {
  const data = isCoordinate
    ? { location: { coordinates: input }, is_coordinates: true }
    : { location: { address: input }, is_coordinates: false };
  const response = await axios.post(
    `${import.meta.env.VITE_BACKEND_SERVER}validate-location`,
    data
  );
  return response.data; // { address, latitude, longitude }
};

// ─── step → human-readable progress (1–5 for the header car) ────────────────

export const stepToProgress = (step) => {
  const map = {
    idle: 1,
    start_input: 1,
    start_validating: 2,
    end_input: 2,
    end_validating: 3,
    fetching_initial: 3,
    stops_input: 3,
    fetching_budget: 4,
    budget_input: 4,
    car_input: 4,
    prefetching_route: 4,
    generating_route: 4,
    done: 5,
    error: 1,
  };
  return map[step] ?? 1;
};

// ─── hook ────────────────────────────────────────────────────────────────────

/**
 * @param {object}   opts
 * @param {number}   opts.chatId        – live chat ID (may change after DB fetch)
 * @param {function} opts.setChats      – context setter
 * @param {function} opts.setCurrentStep – header car progress setter
 * @param {object}   opts.savedData     – ChatData loaded from DB (for resuming)
 * @param {object}   opts.chatsRef      – ref to live chats array
 * @param {string}   opts.accessToken
 * @param {object}   opts.ChatLogsData  – ChatLogs instance
 */
export function useTripWorkflow({
  chatId,
  setChats,
  setCurrentStep,
  savedData,
  chatsRef,
  accessToken,
  ChatLogsData,
}) {
  // ── Derived initial step from savedData (resume support) ─────────────────
  const deriveInitialStep = () => {
    if (!savedData) return 'start_input';
    if (savedData.isComplete || savedData.route) return 'done';
    if (savedData.initial) return 'fetching_budget'; // have initial, need budget
    if (savedData.endConfirmed) return 'fetching_initial';
    if (savedData.startConfirmed) return 'end_input';
    return 'start_input';
  };

  const [step, setStep] = useState(deriveInitialStep);

  // Trip data — plain React state, no class mutations
  const [startConfirmed, setStartConfirmed] = useState(savedData?.startConfirmed ?? null);
  const [endConfirmed, setEndConfirmed] = useState(savedData?.endConfirmed ?? null);
  const [stops, setStops] = useState(savedData?.stops ?? 1);
  const [initial, setInitial] = useState(savedData?.initial ?? null);
  const [hotelBudget, setHotelBudget] = useState(savedData?.hotelBudget ?? 0);
  const [carDetails, setCarDetails] = useState(savedData?.carDetails ?? ['', '', '']);
  const [carBudget, setCarBudget] = useState(savedData?.carBudget ?? 0);
  const [route, setRoute] = useState(savedData?.route ?? null);
  const [itinerary, setItinerary] = useState(savedData?.itinerary ?? null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Pre-fetched final route — kick off in background during car input
  const preFetchRef = useRef(null);
  // Tracks whether the car form has been submitted so the input bar hides immediately
  const carSubmittedRef = useRef(false);
  // Prevents concurrent submit calls (StrictMode double-invoke guard)
  const submitInFlightRef = useRef(false);

  // Keep chatId in a ref so effects always use the live value
  const chatIdRef = useRef(chatId);
  useEffect(() => {
    chatIdRef.current = chatId;
  }, [chatId]);

  // Sync header car position on every step change
  useEffect(() => {
    setCurrentStep(stepToProgress(step));
  }, [step, setCurrentStep]);

  // ── Helper: bot message shorthand ────────────────────────────────────────
  const bot = useCallback((text) => addMessage(chatIdRef.current, setChats, text, BOT), [setChats]);
  const loading = useCallback(
    () => addMessage(chatIdRef.current, setChats, 'loading', BOT),
    [setChats]
  );
  const noLoader = useCallback(() => removeLoader(chatIdRef.current, setChats), [setChats]);

  // ── Build a ChatData-like snapshot for DB persistence ────────────────────
  const buildSnapshot = useCallback(
    () => ({
      chatId: chatIdRef.current,
      action: null,
      locationType: 'start',
      startCoords: startConfirmed ? [startConfirmed.latitude, startConfirmed.longitude] : null,
      startAddress: new Array(4).fill(''),
      endCoords: endConfirmed ? [endConfirmed.latitude, endConfirmed.longitude] : null,
      endAddress: new Array(4).fill(''),
      stops,
      showInputBar: false,
      showStopSlider: false,
      showBudgetSlider: false,
      showAddressInput: false,
      workflowStarted: true,
      startConfirmed,
      endConfirmed,
      initial,
      route,
      itinerary,
      loading: false,
      hotelBudget,
      carBudget,
      carDetails,
      budget: hotelBudget + carBudget,
      isComplete: step === 'done',
    }),
    [
      startConfirmed,
      endConfirmed,
      stops,
      initial,
      route,
      itinerary,
      hotelBudget,
      carBudget,
      carDetails,
      step,
    ]
  );

  const persist = useCallback(async () => {
    await updateUserData(accessToken, buildSnapshot(), chatsRef.current);
  }, [accessToken, buildSnapshot, chatsRef]);

  // ── Step: start_input ─────────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'start_input') return;
    bot('Where are you starting from?');
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step: start_validating ────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'start_validating') return;
    let cancelled = false;
    const run = async () => {
      loading();
      try {
        const result = await validateLocationApi(
          startConfirmed,
          Array.isArray(startConfirmed) // coords vs string
        );
        if (cancelled) return;
        noLoader();
        setStartConfirmed(result);
        bot(`Starting from: ${result.address}`);
        setStep('end_input');
      } catch {
        if (cancelled) return;
        noLoader();
        bot('Could not find that location. Please try again.');
        setStartConfirmed(null);
        setStep('start_input');
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step: end_input ───────────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'end_input') return;
    bot('Where are you headed?');
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step: end_validating ──────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'end_validating') return;
    let cancelled = false;
    const run = async () => {
      loading();
      try {
        const result = await validateLocationApi(endConfirmed, Array.isArray(endConfirmed));
        if (cancelled) return;
        noLoader();
        setEndConfirmed(result);
        bot(`Destination: ${result.address}`);

        // Rename the chat in the list — do this before persisting so the title is correct
        renameChatToRoute(chatIdRef.current, startConfirmed, result, setChats);

        // Build snapshot with the validated result directly (don't rely on state update timing)
        const snap = buildSnapshot();
        snap.endConfirmed = result;
        snap.endCoords = [result.latitude, result.longitude];
        snap.startConfirmed = startConfirmed; // ensure we have the validated object

        // Find the chat log — check chatsRef first, fall back to updated title
        const chatLog = chatsRef.current.find((c) => c.id === chatIdRef.current) ?? null;

        if (chatLog) {
          // Fire-and-forget — don't block the workflow on the DB write
          const endCity = result.address?.split(',').map((p) => p.trim())[1] ?? result.address;
          const namedLog = { ...chatLog, title: `Trip to ${endCity}` };
          createChat(accessToken, snap, namedLog).catch(() => {});
        }

        setStep('fetching_initial');
      } catch {
        if (cancelled) return;
        noLoader();
        bot('Could not find that location. Please try again.');
        setEndConfirmed(null);
        setStep('end_input');
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step: fetching_initial ────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'fetching_initial') return;
    let cancelled = false;
    const run = async () => {
      loading();
      try {
        const result = await getInitialRoute(
          startConfirmed.latitude,
          startConfirmed.longitude,
          endConfirmed.latitude,
          endConfirmed.longitude
        );
        if (cancelled) return;
        noLoader();
        setInitial(result);
        // Build snapshot with result directly — setInitial() is async, don't rely on closure
        const snap = buildSnapshot();
        snap.initial = result;
        await updateUserData(accessToken, snap, chatsRef.current);
        bot('How many attractions would you like to stop at?');
        setStep('stops_input');
      } catch {
        if (cancelled) return;
        noLoader();
        bot('Error fetching route. Please try again.');
        setStep('error');
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step: stops_input — handled by UI (StopSlider submits via submit()) ───

  // ── Step: fetching_budget ─────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'fetching_budget') return;
    let cancelled = false;
    const run = async () => {
      loading();
      try {
        const budget = await calcHotelBudget(initial.duration, stops);
        if (cancelled) return;
        noLoader();
        setHotelBudget(budget);
        if (budget > 0) {
          bot(
            `We estimate your minimum hotel cost to be $${budget}. Would you like to adjust your budget?`
          );
          setStep('budget_input');
        } else {
          // No overnight stay needed — skip budget input
          setStep('car_input');
          bot(
            'No overnight stays needed! Now, what car will you be driving? Enter year, make, and model (e.g. 2020 Mazda CX-3).'
          );
        }
        // Kick off final route pre-fetch in the background
        preFetchRef.current = getFinalRoute(initial, budget, stops).catch(() => null);
      } catch {
        if (cancelled) return;
        noLoader();
        setStep('car_input');
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step: budget_input — UI submits via submit('budget', value) ───────────

  // ── Step: car_input prompt ────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'car_input') return;
    // Message already added by fetching_budget if no hotel needed; skip if budget_input just ran
  }, [step]);

  // ── Step: generating_route ────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 'generating_route') return;
    let cancelled = false;
    const run = async () => {
      loading();
      try {
        let finalRoute = preFetchRef.current ? await preFetchRef.current : null;
        if (!finalRoute) {
          finalRoute = await getFinalRoute(initial, hotelBudget, stops);
        }
        if (cancelled) return;
        if (!finalRoute) throw new Error('No route returned');

        setRoute(finalRoute);

        // Generate itinerary
        const itin = await generateItinerary(finalRoute);
        if (cancelled) return;
        setItinerary(itin);
        noLoader();

        const totalCost = (finalRoute.cost ?? 0) + carBudget;
        const completionMsg = `Your trip is ready! Estimated cost: $${totalCost} (hotel + gas). Use the Map and Itinerary buttons to explore.`;
        bot(completionMsg);

        // Build final snapshot explicitly — never rely on stale state closures
        const snap = buildSnapshot();
        snap.route = finalRoute;
        snap.itinerary = itin;
        snap.isComplete = true;

        // Manually add the completion message to chatsRef so it's included in the DB write.
        // setChats (called by bot()) is async — chatsRef won't reflect it yet.
        chatsRef.current = chatsRef.current.map((c) =>
          c.id === chatIdRef.current
            ? {
                ...c,
                messages: [
                  ...c.messages.filter((m) => m.type !== 'loading-chat'),
                  { text: completionMsg, sender: BOT },
                ],
              }
            : c
        );

        // Save to ChatLogsData in-memory and persist to DB
        const chatIdx = ChatLogsData.chatdata.findIndex((c) => c.chatId === chatIdRef.current);
        if (chatIdx !== -1) ChatLogsData.chatdata[chatIdx] = snap;
        await updateUserData(accessToken, snap, chatsRef.current);

        setStep('done');
      } catch {
        if (cancelled) return;
        noLoader();
        bot('Error generating your route. Please try again.');
        setStep('error');
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Public: submit user input ─────────────────────────────────────────────

  /**
   * Call this from UI event handlers.
   *
   * Actions:
   *   'start_text'   payload: string — free-text location
   *   'start_coords' payload: [lat,lon] — from geolocation API
   *   'end_text'     payload: string
   *   'end_coords'   payload: [lat,lon]
   *   'stops'        payload: number (1–10)
   *   'budget'       payload: number ($)
   *   'car'          payload: [year, make, model]
   */
  const submit = useCallback(
    async (action, payload) => {
      // Guard against StrictMode double-invoke or rapid double-clicks
      if (submitInFlightRef.current) return;
      submitInFlightRef.current = true;

      const id = chatIdRef.current;

      try {
        if (action === 'start_text' && step === 'start_input') {
          addMessage(id, setChats, payload, USER);
          setStartConfirmed(payload);
          setStep('start_validating');
        } else if (action === 'start_coords' && step === 'start_input') {
          addMessage(id, setChats, 'Using current location…', USER);
          setStartConfirmed(payload);
          setStep('start_validating');
        } else if (action === 'end_text' && step === 'end_input') {
          addMessage(id, setChats, payload, USER);
          setEndConfirmed(payload);
          setStep('end_validating');
        } else if (action === 'end_coords' && step === 'end_input') {
          addMessage(id, setChats, 'Using current location…', USER);
          setEndConfirmed(payload);
          setStep('end_validating');
        } else if (action === 'stops' && step === 'stops_input') {
          const n = Math.min(10, Math.max(1, Number(payload)));
          setStops(n);
          addMessage(id, setChats, `${n} stop${n !== 1 ? 's' : ''}`, USER);
          setStep('fetching_budget');
        } else if (action === 'budget' && step === 'budget_input') {
          const b = Math.max(hotelBudget, Number(payload));
          setHotelBudget(b);
          addMessage(id, setChats, `$${b}`, USER);
          bot('What car will you be driving? Enter year, make, and model (e.g. 2020 Mazda CX-3).');
          setStep('car_input');
        } else if (action === 'car' && step === 'car_input') {
          const [year, make, model] = payload;
          setCarDetails([year, make, model]);
          addMessage(id, setChats, `${year} ${make} ${model}`, USER);
          carSubmittedRef.current = true; // hide the input bar immediately

          loading();
          try {
            const snap = buildSnapshot();
            snap.carDetails = [year, make, model];
            const updated = await calcGasBudget(
              initial.distance,
              year,
              make,
              model,
              id,
              setChats,
              snap
            );
            noLoader();
            const cb = updated?.carBudget ?? 0;
            setCarBudget(cb);
            const total = hotelBudget + cb;
            bot(`Total estimated budget: $${total} (hotel: $${hotelBudget}, gas: $${cb})`);
            const carSnap = buildSnapshot();
            carSnap.carDetails = [year, make, model];
            carSnap.carBudget = cb;
            carSnap.budget = hotelBudget + cb;
            await updateUserData(accessToken, carSnap, chatsRef.current);
            setStep('generating_route');
          } catch {
            noLoader();
            carSubmittedRef.current = false; // allow retry
            bot('Could not look up that vehicle. Please try again.');
          }
        }
      } finally {
        submitInFlightRef.current = false;
      }
    },
    [step, hotelBudget, initial, bot, loading, noLoader, buildSnapshot, persist, setChats]
  );

  // ── Which input the UI should render ─────────────────────────────────────
  const inputMode =
    step === 'start_input'
      ? 'location'
      : step === 'end_input'
        ? 'location'
        : step === 'stops_input'
          ? 'stops'
          : step === 'budget_input'
            ? 'budget'
            : step === 'car_input' && !carSubmittedRef.current
              ? 'car'
              : 'none';

  const locationVariant = step === 'start_input' ? 'start' : 'end';

  return {
    step,
    inputMode,
    locationVariant,
    submit,
    // trip data (for MapButton / ItineraryButton)
    route,
    itinerary,
    stops,
    hotelBudget,
    carDetails,
    setCarDetails,
  };
}
