import axios from 'axios';
import { Data, ChatLogs, ChatData } from '../../states/UserDataContext';

// A lifecycle belongs to the account's ChatLogs instance, survives panel remounts,
// and is released when clearUserData replaces that instance. Never key by UI id alone.
const lifecycles = new WeakMap();
const accountKey = (token) => {
  try {
    const claims = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return claims.sub && claims.iss ? `${claims.iss}:${claims.sub}` : token;
  } catch {
    return token;
  }
};
const lifecycleFor = (owner, token) => {
  const account = accountKey(token);
  let lifecycle = lifecycles.get(owner);
  if (!lifecycle || lifecycle.account !== account) {
    lifecycle = { account, ready: new Set(), pending: new Map() };
    lifecycles.set(owner, lifecycle);
  }
  return lifecycle;
};

export const ensureChatCreated = async (token, data, chats, owner) => {
  const lifecycle = lifecycleFor(owner, token);
  if (lifecycle.ready.has(data.chatId)) return true;
  if (!lifecycle.pending.has(data.chatId)) {
    const chat = chats.find((item) => item.id === data.chatId);
    if (!token || !chat) return false;
    const promise = createChat(token, data, chat).then((created) => {
      if (created) lifecycle.ready.add(data.chatId);
      lifecycle.pending.delete(data.chatId);
      return created;
    });
    lifecycle.pending.set(data.chatId, promise);
  }
  const created = await lifecycle.pending.get(data.chatId);
  return created && lifecycles.get(owner) === lifecycle;
};

export const createChat = async (auth_token, UserChatData, ChatLog) => {
  try {
    // Sanitize the chat log — loading bubbles have no text/sender and fail backend validation
    const sanitizedLog = ChatLog
      ? { ...ChatLog, messages: (ChatLog.messages ?? []).filter((m) => m.type !== 'loading-chat') }
      : ChatLog;
    const data = {
      PartitionKey: auth_token,
      ChatData: UserChatData,
      ChatLog: sanitizedLog,
    };
    console.debug('[DB] createChat chatId=%s', UserChatData.chatId);
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}chats/create/${UserChatData.chatId}`,
      data
    );
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
    return false;
  }
};

export const deleteChat = async (auth_token, chatId, owner) => {
  if (owner) lifecycleFor(owner, auth_token).ready.delete(chatId);
  try {
    await axios.delete(`${import.meta.env.VITE_BACKEND_SERVER}chats/delete/${chatId}`, {
      headers: { Authorization: `Bearer ${auth_token}` },
    });
    return null;
  } catch (error) {
    console.error('Failed to delete chat; status=%s', error.response?.status ?? 'network');
    return null;
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
      restored.tripProfile = chat_d.tripProfile ?? {};
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

export const updateUserData = async (access_token, UserChatData, chats, owner) => {
  if (owner && !(await ensureChatCreated(access_token, UserChatData, chats, owner))) return false;
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
  const data = {
    PartitionKey: access_token,
    ChatData: UserChatData,
    ChatLog: sanitizedChat,
  };
  try {
    const response = await axios.put(
      `${import.meta.env.VITE_BACKEND_SERVER}chats/update/${UserChatData.chatId}`,
      data
    );
    console.debug(
      '[DB] updateUserData success chatId=%s status=%s',
      UserChatData.chatId,
      response.status
    );
    return true;
  } catch (error) {
    if (error.response?.status === 404) {
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
