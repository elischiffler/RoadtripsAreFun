import React, { createContext, useState } from "react";

const UserDataContext = createContext();

class Data {
  constructor() {
    this.chatlogs = new ChatLogs();
  }
}

class ChatLogs {
  constructor() {
    this.chatdata = []; // Start with an empty array
  }

  // Method to find a specific ChatData by chatId
  getChatDataById(chatId) {
    return this.chatdata.find(chat => chat.chatId === chatId);
  }

  // Method to add a new ChatData instance
  addChatData(chatData) {
    this.chatdata.push(chatData);
  }

  // Method to create and add a new ChatData instance
  createChatData(chatId) {
    const newChatData = new ChatData(chatId);
    this.addChatData(newChatData);
    return newChatData;
  }
}


class ChatData {
  constructor(chatId = null) {
    this.chatId = chatId;
    this.action = null;
    this.locationType = "start";
    this.startCoords = new Array(2).fill(0);
    this.startAddress = new Array(4).fill("");
    this.endCoords = new Array(2).fill(0);
    this.endAddress = new Array(4).fill("");
    this.submitted = false;
    this.stops = [];
    this.showStopSlider = false;
    this.showAddressInput = false;
    this.workflowStarted = false;
  }
}

export const UserDataProvider = ({ children }) => {
  const [UserData] = useState(new Data()); // Initialize the global UserData instance

  return (
    <UserDataContext.Provider value={UserData}>
      {children}
    </UserDataContext.Provider>
  );
};

export { UserDataContext };
