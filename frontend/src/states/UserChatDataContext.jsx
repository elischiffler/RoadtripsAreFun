import React, { createContext, useState } from "react";

const UserChatDataContext = createContext();

class ChatData {
  constructor() {
    this.action = null;
    this.coords = new Array(2).fill(0);
    this.address = new Array(4).fill("");
    this.submitted = false;
  }
}

export const UserChatDataProvider = ({ children }) => {
  const [UserChatData] = useState(new ChatData()); // Initialize the global UserChatData instance

  return (
    <UserChatDataContext.Provider value={UserChatData}>
      {children}
    </UserChatDataContext.Provider>
  );
};

export { UserChatDataContext };
