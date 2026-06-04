import { createContext, useState } from 'react';
import PropTypes from 'prop-types';

const UserDataContext = createContext();

class Data {
  constructor(chatlogs = new ChatLogs()) {
    this.chatlogs = chatlogs;
  }
}

class ChatLogs {
  constructor(chatdata = [], currentId = 1) {
    this.chatdata = chatdata; // Start with an empty array
    this.currentId = currentId;
  }

  // Method to find a specific ChatData by chatId
  getChatDataById(chatId) {
    return this.chatdata.find((chat) => chat.chatId === chatId);
  }

  // Method to add a new ChatData instance
  addChatData(chatData) {
    this.chatdata.push(chatData);
  }

  // Method to create and add a new ChatData instance
  createChatData(chatId) {
    const newChatData = new ChatData(chatId);
    const index = this.chatdata.findIndex((chat) => chat.chatId === chatId);
    if (index !== -1) {
      // check if there already is this chatId
      this.chatdata[index] = newChatData; // replace the outdated version
    } else {
      this.addChatData(newChatData); // add a new instance to the end of the chat list
    }
    return newChatData;
  }

  removeChatData(chatId) {
    this.chatdata = this.chatdata.filter((ChatData) => ChatData.chatId !== chatId);
  }
}

class ChatData {
  constructor(
    chatId = null, // Constructor gives initial values if not provided/ defines possible input parameters
    action = null,
    locationType = 'start',
    startCoords = null,
    startAddress = new Array(4).fill(''),
    endCoords = null,
    endAddress = new Array(4).fill(''),
    stops = 1,
    showInputBar = false,
    showStopSlider = false,
    showBudgetSlider = false,
    showAddressInput = false,
    workflowStarted = false,
    startConfirmed = null,
    endConfirmed = null,
    initial = null,
    route = null,
    itinerary = null,
    loading = false,
    hotelBudget = null,
    carBudget = 0,
    carDetails = new Array(3).fill(''),
    budget = 0,
    isComplete = false
  ) {
    this.chatId = chatId;
    this.action = action;
    this.locationType = locationType;
    this.startCoords = startCoords;
    this.startAddress = startAddress;
    this.endCoords = endCoords;
    this.endAddress = endAddress;
    this.stops = stops;
    this.showInputBar = showInputBar;
    this.showStopSlider = showStopSlider;
    this.showBudgetSlider = showBudgetSlider;
    this.showAddressInput = showAddressInput;
    this.workflowStarted = workflowStarted;
    this.startConfirmed = startConfirmed;
    this.endConfirmed = endConfirmed;
    this.initial = initial;
    this.route = route;
    this.itinerary = itinerary;
    this.loading = loading;
    this.hotelBudget = hotelBudget;
    this.carBudget = carBudget;
    this.carDetails = carDetails;
    this.budget = budget;
    this.isComplete = isComplete;
  }
}

export { Data, ChatLogs, ChatData };

export const UserDataProvider = ({ children }) => {
  // Initializes global instance of UserData
  const [UserData, setUserData] = useState(new Data());
  const [chats, setChats] = useState([]);

  return (
    <UserDataContext.Provider value={{ UserData, setUserData, chats, setChats }}>
      {children}
    </UserDataContext.Provider>
  );
};

UserDataProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export { UserDataContext };
