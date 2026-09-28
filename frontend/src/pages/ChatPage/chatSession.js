const agentKey = (chatId) => `roadtrips.agentChatId.${chatId}`;

export const chooseRestoredChatId = (storedId, savedChats, freshId) =>
  savedChats.some((chat) => chat.id === storedId) ? storedId : freshId;

export const getOrCreateAgentChatId = (chatId, chatData, cache, storage = sessionStorage) => {
  let agentId = cache.get(chatId);
  if (!agentId) {
    agentId =
      chatData?.agentChatId ||
      storage.getItem(agentKey(chatId)) ||
      (typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `agent-${chatId}-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    cache.set(chatId, agentId);
    storage.setItem(agentKey(chatId), agentId);
  }
  if (chatData) chatData.agentChatId = agentId;
  return agentId;
};

export const forgetAgentChatId = (chatId, cache, storage = sessionStorage) => {
  cache.delete(chatId);
  storage.removeItem(agentKey(chatId));
};
