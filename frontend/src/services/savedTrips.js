import axios from './protectedRequest';
import { getSession, isCurrentSession, SessionError, tokenOwner } from './session';
import { Data, ChatLogs, ChatData } from '../states/UserDataContext';

// A lifecycle belongs to the account's ChatLogs instance, survives panel remounts,
// and is released when clearUserData replaces that instance. Never key by UI id alone.
const lifecycles = new WeakMap();
const accountKey = (token) => tokenOwner(token) || getSession().owner;
const lifecycleFor = (owner, token) => {
  const account = accountKey(token);
  let lifecycle = lifecycles.get(owner);
  if (!lifecycle || lifecycle.account !== account) {
    lifecycle = {
      account,
      ready: new Set(),
      identities: new Map(),
      guidedIds: new Map(),
      pending: new Map(),
    };
    lifecycles.set(owner, lifecycle);
  }
  return lifecycle;
};

const planningIdentity = (data) =>
  typeof data.agentChatId === 'string' && data.agentChatId.trim() ? data.agentChatId : null;
const IDENTITY_CONFLICT = 'Trip ID belongs to a different planning request';

function freshTripId(reserved) {
  if (typeof crypto?.getRandomValues !== 'function') return null;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    let words;
    try {
      words = crypto.getRandomValues(new Uint32Array(2));
    } catch {
      return null;
    }
    // 48 bits leave room for future sequential max-loaded-ID + 1 allocation.
    const id = (words[0] & 0xffff) * 0x100000000 + words[1];
    if (Number.isSafeInteger(id) && id > 0 && id < Number.MAX_SAFE_INTEGER && !reserved.has(id))
      return id;
  }
  return null;
}

function alignCreatedId(data, chats, id) {
  const originals = chats.filter((item) => item.id === data.chatId);
  const targets = chats.filter((item) => item.id === id);
  if (originals.length > 1 || targets.length > 1) return false;
  const record = originals[0] || targets[0];
  if (!record || (targets[0] && targets[0] !== record)) return false;
  data.chatId = id;
  record.id = id;
  return true;
}

export const ensureChatCreated = async (token, data, chats, owner) => {
  const session = getSession();
  if (tokenOwner(token) && tokenOwner(token) !== session.owner)
    throw new SessionError('session-changed');
  const lifecycle = lifecycleFor(owner, token);
  const identity = planningIdentity(data);
  const active = () => isCurrentSession(session) && lifecycles.get(owner) === lifecycle;
  const knownId = identity ? lifecycle.guidedIds.get(identity) : undefined;
  if (
    knownId !== undefined &&
    lifecycle.ready.has(knownId) &&
    lifecycle.identities.get(knownId) === identity
  ) {
    return active() && alignCreatedId(data, chats, knownId);
  }
  const restored = owner?.chatdata?.find((item) => item.chatId === data.chatId);
  const readyIdentity = lifecycle.identities.has(data.chatId)
    ? lifecycle.identities.get(data.chatId)
    : restored
      ? planningIdentity(restored)
      : null;
  if (lifecycle.ready.has(data.chatId) && readyIdentity === identity) return true;
  const pendingKey = identity ? `guided:${identity}` : data.chatId;
  if (!lifecycle.pending.has(pendingKey)) {
    const matching = chats.filter((item) => item.id === data.chatId);
    if (!token || matching.length !== 1) return false;
    const chat = matching[0];
    const operation = { data, promise: null };
    operation.promise = createChat(token, data, chat, {
      retryIdentityConflicts: identity !== null,
      reservedIds: new Set([
        ...chats.map((item) => item.id),
        ...(owner?.chatdata ?? []).map((item) => item.chatId),
      ]),
    })
      .then((created) => {
        if (created && active()) {
          lifecycle.ready.add(data.chatId);
          lifecycle.identities.set(data.chatId, identity);
          if (identity) lifecycle.guidedIds.set(identity, data.chatId);
        }
        return created;
      })
      .finally(() => {
        if (lifecycle.pending.get(pendingKey) === operation) lifecycle.pending.delete(pendingKey);
      });
    lifecycle.pending.set(pendingKey, operation);
  }
  const operation = lifecycle.pending.get(pendingKey);
  const created = await operation.promise;
  if (!created || !active()) return false;
  return (
    data.chatId === operation.data.chatId || alignCreatedId(data, chats, operation.data.chatId)
  );
};

// Only the guided ensure-created path opts into collision recovery. Legacy
// direct creates and a missing-row update retain their original single attempt.
export const createChat = async (auth_token, UserChatData, ChatLog, options = {}) => {
  const session = getSession();
  const identity = planningIdentity(UserChatData);
  const reserved = new Set(options.reservedIds ?? []);
  reserved.add(UserChatData.chatId);
  const maxAttempts = options.retryIdentityConflicts && identity ? 3 : 1;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (!isCurrentSession(session)) return false;
    try {
      const sanitizedLog = ChatLog
        ? {
            ...ChatLog,
            messages: (ChatLog.messages ?? []).filter((m) => m.type !== 'loading-chat'),
          }
        : ChatLog;
      const data = {
        PartitionKey: auth_token,
        // Snapshot IDs per dispatch; a later safe retry must not mutate a
        // previously dispatched request or its diagnostic/mock representation.
        ChatData: { ...UserChatData },
        ChatLog: sanitizedLog,
      };
      console.debug('[DB] createChat chatId=%s', UserChatData.chatId);
      const response = await axios.post(
        `${import.meta.env.VITE_BACKEND_SERVER}chats/create/${UserChatData.chatId}`,
        data
      );
      if (!isCurrentSession(session)) return false;
      UserChatData.savedRevision = response.headers?.['x-trip-revision'] ?? null;
      console.debug(
        '[DB] createChat success chatId=%s status=%s',
        UserChatData.chatId,
        response.status
      );
      return true;
    } catch (error) {
      console.error(
        '[DB] createChat failed chatId=%s status=%s',
        UserChatData.chatId,
        error.response?.status ?? 'network'
      );
      if (
        isCurrentSession(session) &&
        error.response?.status === 409 &&
        error.response?.data?.detail === 'Trip already saved; reload before continuing'
      ) {
        UserChatData.saveConflict = true;
        return false;
      }
      if (
        !isCurrentSession(session) ||
        attempt + 1 >= maxAttempts ||
        error.response?.status !== 409 ||
        error.response?.data?.detail !== IDENTITY_CONFLICT
      )
        return false;
      const id = freshTripId(reserved);
      if (id === null) return false;
      reserved.add(id);
      UserChatData.chatId = id;
      ChatLog.id = id;
    }
  }
  return false;
};

export const deleteChat = async (auth_token, chatId, owner) => {
  const session = getSession();
  try {
    await axios.delete(`${import.meta.env.VITE_BACKEND_SERVER}chats/delete/${chatId}`, {
      headers: { Authorization: `Bearer ${auth_token}` },
    });
    if (!isCurrentSession(session)) return false;
    if (owner) lifecycleFor(owner, auth_token).ready.delete(chatId);
    return true;
  } catch (error) {
    console.error('Failed to delete chat; status=%s', error.response?.status ?? 'network');
    return false;
  }
};

export const initializeUserData = async (auth_token) => {
  try {
    const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}chats`, {
      headers: { Authorization: `Bearer ${auth_token}` },
    });
    const user_data = response.data;
    const chats = [];
    const chatdata = [];
    for (const entry of user_data) {
      chats.push(entry[1]);
      const chat_d = entry[0];
      const restored = new ChatData(
        chat_d['chatId'],
        chat_d['action'],
        chat_d['locationType'],
        chat_d['startCoords'],
        chat_d['startAddress'],
        chat_d['endCoords'],
        chat_d['endAddress'],
        chat_d['stops'],
        chat_d['showInputBar'],
        chat_d['showStopSlider'],
        chat_d['showBudgetSlider'],
        chat_d['showAddressInput'],
        false,
        chat_d['startConfirmed'],
        chat_d['endConfirmed'],
        chat_d['initial'],
        chat_d['route'],
        chat_d['itinerary'],
        false,
        chat_d['hotelBudget'],
        chat_d['carBudget'],
        chat_d['carDetails'],
        chat_d['budget'],
        chat_d['isComplete'] || false,
        chat_d['agentChatId'] || null
      );
      restored.savedRevision = chat_d.savedRevision ?? null;
      restored.tripProfile = chat_d.tripProfile ?? {};
      restored.presentation =
        chat_d.presentation &&
        typeof chat_d.presentation === 'object' &&
        !Array.isArray(chat_d.presentation)
          ? chat_d.presentation
          : {};
      chatdata.push(restored);
    }
    const logs = new ChatLogs(chatdata);
    const UserData = new Data(logs);
    const lifecycle = lifecycleFor(logs, auth_token);
    chatdata.forEach((chat) => lifecycle.ready.add(chat.chatId));
    return { chats: chats, UserData: UserData };
  } catch (error) {
    console.error('Error retrieving saved chats; status=%s', error.response?.status ?? 'network');
    return null;
  }
};

export const updateUserData = async (access_token, UserChatData, chats, owner, options = {}) => {
  const session = getSession();
  if (
    !options.presentationOnly &&
    owner &&
    !(await ensureChatCreated(access_token, UserChatData, chats, owner))
  )
    return false;
  const newChat = chats.find(
    (
      Chat // Find the currently selected chat in chats
    ) => Chat.id === UserChatData.chatId
  );

  if (!newChat) {
    console.warn(
      '[DB] updateUserData: no chat found in chats array for chatId=%s — available ids: %s',
      UserChatData.chatId,
      chats.map((c) => c.id).join(', ')
    );
    return false;
  }

  // Sanitize the chat log to ensure no loading animations are sent to the backend
  const sanitizedChat = {
    ...newChat,
    messages: newChat.messages.filter((msg) => msg.type !== 'loading-chat'),
  };

  console.debug(
    '[DB] updateUserData chatId=%s messages=%d',
    UserChatData.chatId,
    sanitizedChat.messages.length
  );
  let revision = UserChatData.savedRevision;
  if (options.presentationOnly && !revision) {
    const loaded = await initializeUserData(access_token);
    if (!isCurrentSession(session)) return false;
    const latest = loaded?.UserData.chatlogs.getChatDataById(UserChatData.chatId);
    if (
      !latest ||
      latest.agentChatId !== UserChatData.agentChatId ||
      JSON.stringify(latest.route) !== JSON.stringify(UserChatData.route) ||
      JSON.stringify(latest.itinerary) !== JSON.stringify(UserChatData.itinerary)
    )
      return false;
    revision = latest.savedRevision;
  }
  if (options.presentationOnly && !/^[0-9a-f]{64}$/.test(revision ?? '')) return false;
  const data = {
    PartitionKey: access_token,
    ChatData: UserChatData,
    ChatLog: sanitizedChat,
    ...(revision
      ? {
          ExpectedRevision: revision,
          UpdateScope: options.presentationOnly ? 'presentation' : 'full',
        }
      : {}),
  };
  try {
    const response = await axios.put(
      `${import.meta.env.VITE_BACKEND_SERVER}chats/update/${UserChatData.chatId}`,
      data
    );
    if (!isCurrentSession(session)) return false;
    if (revision) UserChatData.savedRevision = response.data?.savedRevision ?? null;
    console.debug(
      '[DB] updateUserData success chatId=%s status=%s',
      UserChatData.chatId,
      response.status
    );
    return true;
  } catch (error) {
    if (isCurrentSession(session) && revision && [404, 409].includes(error.response?.status))
      UserChatData.saveConflict = true;
    if (error.response?.status === 404 && !options.presentationOnly && !revision) {
      // Recover a genuinely stale/deleted row; ordinary new trips create before PUT.
      return createChat(access_token, UserChatData, sanitizedChat);
    }
    console.error(
      '[DB] updateUserData failed chatId=%s status=%s',
      UserChatData.chatId,
      error.response?.status ?? 'network'
    );
    return false;
  }
};
