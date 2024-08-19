import React, { createContext, useState } from "react";

const UserDataContext = createContext();

class Data {
  constructor() {
    this.chat = new ChatData();
  }
}

class ChatData {
  constructor() {
    this.chatId = null;
    this.action = null;
    this.locationType = "start";
    this.startCoords = new Array(2).fill(0);
    this.startAddress = new Array(4).fill("");
    this.endCoords = new Array(2).fill(0);
    this.endAddress = new Array(4).fill("");
    this.submitted = false;
    this.stops = null;
    this.showStopSlider = false;
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
