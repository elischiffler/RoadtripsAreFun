import request from './protectedRequest';
import { initializeUserData } from './savedTrips';
import { getSession, isCurrentSession } from './session';

// Keep uncertain writes attached to the account context across page remounts.
const pending = new WeakMap();
export const pendingTripEdit = (logs, id) => pending.get(logs)?.get(id);
const remember = (logs, id, value) => {
  if (!pending.has(logs)) pending.set(logs, new Map());
  if (value) pending.get(logs).set(id, value);
  else pending.get(logs).delete(id);
};
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .filter((key) => value[key] !== undefined)
        .map((key) => [key, canonical(value[key])])
    );
  return value;
};
const persistedFields = (trip) =>
  canonical({
    agentChatId: trip.agentChatId ?? null,
    route: trip.route,
    itinerary: trip.itinerary,
    presentation: trip.presentation ?? {},
    stops: trip.stops,
    tripProfile: trip.tripProfile ?? {},
    carDetails: trip.carDetails ?? [],
    carBudget: trip.carBudget ?? null,
  });
const matches = (left, right) =>
  JSON.stringify(persistedFields(left)) === JSON.stringify(persistedFields(right));

export async function previewTripEdit(trip, place, action, stopIndex, signal) {
  const response = await request.post(
    `${import.meta.env.VITE_BACKEND_SERVER}route-edit`,
    {
      route: trip.route,
      provider_id: place.provider_id || place.id,
      action,
      stop_index: stopIndex,
      include_meal_slots: (trip.itinerary || []).some((day) =>
        (day.stops || []).some((stop) => stop.kind === 'meal')
      ),
    },
    { signal }
  );
  if (!response.data?.route || !Array.isArray(response.data.itinerary))
    throw new Error('Trip preview unavailable.');
  return response.data;
}

export function editedTripSnapshot(original, preview) {
  const oldCount = (original.route?.stops || []).filter((stop) => stop.type === 'stop').length;
  const count = (preview.route.stops || []).filter((stop) => stop.type === 'stop').length;
  return {
    ...original,
    route: preview.route,
    itinerary: preview.itinerary,
    presentation: { ...original.presentation, visitedStopIds: [] },
    ...(oldCount === count
      ? {}
      : { stops: count, tripProfile: { ...original.tripProfile, num_stops: count } }),
  };
}

export async function reconcileTripEdit(logs, id, session = getSession()) {
  const operation = pendingTripEdit(logs, id);
  if (!operation) return { status: 'unchanged' };
  let loaded;
  try {
    loaded = await initializeUserData(session.accessToken);
  } catch {
    /* Outcome remains uncertain. */
  }
  if (!isCurrentSession(session)) return { status: 'stale' };
  const saved = loaded?.UserData?.chatlogs?.getChatDataById(id);
  if (saved && matches(saved, operation.snapshot)) {
    remember(logs, id, null);
    return {
      status: 'saved',
      snapshot: { ...operation.snapshot, savedRevision: saved.savedRevision },
    };
  }
  return { status: 'uncertain' };
}

export async function persistTripEdit(original, snapshot, chats, logs, session = getSession()) {
  if (pendingTripEdit(logs, original.chatId)) return { status: 'uncertain' };
  if (!isCurrentSession(session)) return { status: 'stale' };
  let current;
  try {
    current = await initializeUserData(session.accessToken);
  } catch {
    /* Do not dispatch without a preflight. */
  }
  if (!isCurrentSession(session)) return { status: 'stale' };
  const latest = current?.UserData?.chatlogs?.getChatDataById(original.chatId);
  if (!current) return { status: 'unavailable' };
  if (
    !latest ||
    !matches(latest, original) ||
    (original.savedRevision && original.savedRevision !== latest.savedRevision)
  )
    return { status: 'conflict' };
  if (!/^[0-9a-f]{64}$/.test(latest.savedRevision ?? '')) return { status: 'unavailable' };
  const chat =
    current.chats.find((item) => item.id === original.chatId) ||
    chats.find((item) => item.id === original.chatId);
  if (!chat) return { status: 'conflict' };
  if (pendingTripEdit(logs, original.chatId)) return { status: 'uncertain' };
  remember(logs, original.chatId, { original, snapshot });
  let saved = false;
  try {
    const response = await request.put(
      `${import.meta.env.VITE_BACKEND_SERVER}chats/update/${original.chatId}`,
      {
        PartitionKey: session.accessToken,
        ExpectedRevision: latest.savedRevision,
        ChatData: snapshot,
        ChatLog: {
          ...chat,
          messages: (chat.messages || []).filter((message) => message.type !== 'loading-chat'),
        },
      }
    );
    snapshot = { ...snapshot, savedRevision: response.data?.savedRevision ?? null };
    saved = true;
  } catch (error) {
    if (isCurrentSession(session) && [404, 409].includes(error.response?.status)) {
      remember(logs, original.chatId, null);
      return { status: 'conflict' };
    }
    /* Read back before any retry. Never recreate a missing trip. */
  }
  if (!isCurrentSession(session)) return { status: 'stale' };
  if (saved) {
    remember(logs, original.chatId, null);
    return { status: 'saved', snapshot };
  }
  return reconcileTripEdit(logs, original.chatId, session);
}
