import axios from 'axios';
import { addMessage, removeLoader, inputLocationDirect } from './startWorkFlow';

// Sends an API request to our backend to validate the location
export const validateLocation = async (
  input,
  isCoordinate,
  UserChatData,
  setChats,
  setChatInput,
  chatInput,
  overrideChatId = null // use this when UserChatData.chatId may be stale
) => {
  const chatId = overrideChatId ?? UserChatData.chatId;
  try {
    const data = isCoordinate
      ? { location: { coordinates: input }, is_coordinates: isCoordinate }
      : { location: { address: input }, is_coordinates: isCoordinate };

    addMessage(chatId, setChats, 'loading', 'bot');
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}validate-location`,
      data
    );
    removeLoader(chatId, setChats);

    const location = response.data;
    console.log('Validated Location:', location);
    return location;
  } catch (error) {
    removeLoader(chatId, setChats);
    console.error('Error validating location:', error);
    addMessage(chatId, setChats, 'Error finding the location. Please try again.', 'bot');

    UserChatData.action = null;
    inputLocationDirect(chatId, setChats, setChatInput, chatInput, UserChatData);
  }
};
