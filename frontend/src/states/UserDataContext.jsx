import React, { createContext, useState, useEffect } from "react";

const UserDataContext = createContext();

class Data {
  constructor(chatlogs = new ChatLogs()) {
    this.chatlogs = chatlogs;
  }
}

class ChatLogs {
  constructor(chatdata = [], currentId = 1) {
    this.chatdata = chatdata;
    this.currentId = currentId;
  }

  getChatDataById(chatId) {
    return this.chatdata.find(chat => chat.chatId === chatId);
  }

  addChatData(chatData) {
    this.chatdata.push(chatData);
  }

  createChatData(chatId) {
    const newChatData = new ChatData(chatId);
    this.addChatData(newChatData);
    return newChatData;
  }
}

class ChatData {
  constructor({
    chatId = null,
    action = null,
    locationType = "start",
    startCoords = [0, 0],
    startAddress = ["", "", "", ""],
    endCoords = [0, 0],
    endAddress = ["", "", "", ""],
    stops = 1,
    showInputBar = true,
    showStopSlider = false,
    showAddressInput = false,
    workflowStarted = false,
    startConfirmed = null,
    endConfirmed = null,
    route = null,
    itinerary = null,
  } = {}) {
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
    this.showAddressInput = showAddressInput;
    this.workflowStarted = workflowStarted;
    this.startConfirmed = startConfirmed;
    this.endConfirmed = endConfirmed;
    this.route = route;
    this.itinerary = itinerary;
  }
}

export const UserDataProvider = ({ children }) => {
  const [UserData, setUserData] = useState(() => {
    const savedData = sessionStorage.getItem("UserData");
    if (savedData) {
      // Deserialize and reconstruct the instance
      const parsedData = JSON.parse(savedData);

      const chatlogs = new ChatLogs(
        parsedData.chatlogs.chatdata.map(chat => new ChatData(chat)),
        parsedData.chatlogs.currentId
      );

      return new Data(chatlogs);
    }

    return new Data(); // Initialize a new instance if none exists in sessionStorage
  });

  useEffect(() => {
    // Serialize and save the instance whenever it changes
    sessionStorage.setItem(
      "UserData",
      JSON.stringify({
        chatlogs: {
          chatdata: UserData.chatlogs.chatdata,
          currentId: UserData.chatlogs.currentId,
        },
      })
    );
  }, [UserData]);

  return (
    <UserDataContext.Provider value={UserData}>
      {children}
    </UserDataContext.Provider>
  );
};

export { UserDataContext };