import React, { createContext, useState, useEffect } from "react";

const UserDataContext = createContext();

class Data {
  constructor(chatlogs = new ChatLogs()) {
    this.chatlogs = chatlogs;
  }
}

class ChatLogs {
  constructor(chatdata = [], currentId = 1,) {
    this.chatdata = chatdata; // Start with an empty array
    this.currentId = currentId;
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
  constructor(chatId = null,
    action = null,
    locationType = "start",
    startCoords = new Array(2).fill(0),
    startAddress = new Array(4).fill(""),
    endCoords = new Array(2).fill(0),
    endAddress = new Array(4).fill(""),
    stops = 1,
    showInputBar = true,
    showStopSlider = false,
    showAddressInput = false,
    workflowStarted = false,
    startConfirmed = null,
    endConfirmed = null,
    route = null,
    itinerary = null,
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
      console.log('parsed data: ', parsedData);
      const chatdata = [];

      if (Array.isArray(parsedData.chatlogs.chatdata)) {
        for (const chat of parsedData.chatlogs.chatdata) {
          chatdata.push(new ChatData(
            chat.chatId,
            chat.action,
            chat.locationType,
            chat.startCoords,
            chat.startAddress,
            chat.endCoords,
            chat.endAddress,
            chat.stops,
            chat.showInputBar,
            chat.showStopSlider,
            chat.showAddressInput,
            chat.workflowStarted,
            chat.startConfirmed,
            chat.endConfirmed,
            chat.route,
            chat.itinerary
          ));
        }
      }

      const chatlogs = new ChatLogs(chatdata, parsedData.chatlogs.currentId);
      console.log("Parsed logs: ", chatlogs);
      var loadedData = new Data(chatlogs);
      console.log('Loaded saved data from sessionStorage: ', loadedData);
      return loadedData;
    }
    console.log('Created a new UserData instance');
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
    console.log("Saved data to sessionStorage: ", UserData);
  }, [UserData]);

  return (
    <UserDataContext.Provider value={UserData}>
      {children}
    </UserDataContext.Provider>
  );
};

export { UserDataContext };