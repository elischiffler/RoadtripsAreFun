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
    if(this.getChatDataById(chatId)){ // check if there alread is this chatId
      this.chatdata[chatId-1] = newChatData; // replace the outdated version
    }
    else{
      this.addChatData(newChatData); // add a new instance to the end of the chat list
    };
    return newChatData;
  }

  removeChatData(chatId){
    this.chatdata = this.chatdata.filter(ChatData => ChatData.chatId !== chatId);
  }
}


class ChatData {
  constructor(chatId = null, // Constructor gives initial values if not provided/ defines possible input parameters
    action = null,
    locationType = "start",
    startCoords = new Array(2).fill(0),
    startAddress = new Array(4).fill(""),
    endCoords = new Array(2).fill(0),
    endAddress = new Array(4).fill(""),
    stops = 1,
    showInputBar = true,
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
    budget = 0,
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
    this.carBudget = carBudget
    this.budget = budget;
  }
}

export {Data, ChatLogs};

export const UserDataProvider = ({ children }) => {
  // Function to retrieve UserData from the sessionStorage
  const getUserData = () => {
    const savedData = sessionStorage.getItem("UserData");
    if (savedData) {
      const parsedData = JSON.parse(savedData);
      const chatdata = parsedData.chatlogs.chatdata.map(chat => new ChatData(
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
        chat.showBudgetSlider,
        chat.showAddressInput,
        false,
        chat.startConfirmed,
        chat.endConfirmed,
        chat.initial,
        chat.route,
        chat.itinerary,
        false, 
        chat.minHotelBudget,
        chat.budget,
      ));
      const chatlogs = new ChatLogs(chatdata, parsedData.chatlogs.currentId);
      const UserData = new Data(chatlogs);
      console.log('Loaded saved data from sessionStorage: ', UserData);
      return UserData
    }
    console.log('Created a new UserData instance');
    return new Data();
  };

  // initializes gloval instance of UserData
  const [UserData, setUserData] = useState(getUserData());

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
    <UserDataContext.Provider value={{UserData, getUserData}}>
      {children}
    </UserDataContext.Provider>
  );
};

export { UserDataContext };