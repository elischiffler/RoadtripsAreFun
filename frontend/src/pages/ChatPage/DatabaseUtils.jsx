import axios from 'axios';
import { Data, ChatLogs, ChatData } from '../../states/UserDataContext';

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
    console.debug('[DB] createChat chatId=%s', UserChatData.chatId, {
      ChatData: UserChatData,
      ChatLog: sanitizedLog,
    });
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}chats/create/${UserChatData.chatId}`,
      data
    );
    console.debug(
      '[DB] createChat success chatId=%s status=%s',
      UserChatData.chatId,
      response.status
    );
    return null;
  } catch (error) {
    console.error(
      '[DB] createChat failed chatId=%s status=%s:',
      UserChatData.chatId,
      error.response?.status,
      JSON.stringify(error.response?.data ?? error.message, null, 2)
    );
    return null;
  }
};

export const deleteChat = async (auth_token, chatId) => {
  try {
    const params = {
      partition_key: auth_token,
    };
    await axios.delete(`${import.meta.env.VITE_BACKEND_SERVER}chats/delete/${chatId}`, { params });
    return null;
  } catch (error) {
    console.error('Failed to delete chat:', error);
    return null;
  }
};

export const initializeUserData = async (auth_token) => {
  try {
    const params = {
      partition_key: auth_token,
    };
    const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}chats`, {
      params: params,
    });
    const user_data = response.data;
    const chats = [];
    const chatdata = [];
    for (const entry of user_data) {
      chats.push(entry[1]);
      const chat_d = entry[0];
      chatdata.push(
        new ChatData(
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
          chat_d['isComplete'] || false
        )
      );
    }
    const logs = new ChatLogs(chatdata);
    const UserData = new Data(logs);
    return { chats: chats, UserData: UserData };
  } catch (error) {
    console.error('Error retrieving saved chats:', error);
    return null;
  }
};

export const updateUserData = async (access_token, UserChatData, chats) => {
  try {
    let newChat = chats.find(
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
      return null;
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
    const response = await axios.put(
      `${import.meta.env.VITE_BACKEND_SERVER}chats/update/${UserChatData.chatId}`,
      data
    );
    console.debug(
      '[DB] updateUserData success chatId=%s status=%s',
      UserChatData.chatId,
      response.status
    );
    return null;
  } catch (error) {
    console.error(
      '[DB] updateUserData failed chatId=%s status=%s:',
      UserChatData.chatId,
      error.response?.status,
      error.response?.data ?? error.message
    );
    return null;
  }
};
