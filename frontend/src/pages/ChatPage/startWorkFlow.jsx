// Helper Function

// Function that gets the user's current location
const getCurrentLocation = (callback) => {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        callback(position.coords.latitude, position.coords.longitude);
      },
      (error) => {
        console.error("Error getting location:", error);
      }
    );
  } else {
    console.error("Geolocation is not supported by this browser.");
  }
};

// Sends an API request to our backend catching errors as needed
const validateLocation = async (start, isCoordinate = false) => {
  try {
    const queryParam = isCoordinate
      ? `coordinates=${encodeURIComponent(start)}`
      : `address=${encodeURIComponent(start)}`;
    const response = await fetch(`/validate-location?${queryParam}`);

    if (!response.ok) {
      throw new Error("Network response was not ok");
    }

    const location = await response.text();
    console.log("Validated Location:", location);

    // Handle the response data as needed
    return location;
  } catch (error) {
    console.error("Error validating location:", error);
  }
};

//
const changePrevious = (chatId, setChats, newMessage) => {
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: (chat.messages || []).map((message) =>
              typeof message === "object" &&
              message.text === "I would like to use my:"
                ? {
                    ...message,
                    text: newMessage,
                    buttons: [], // Remove buttons
                  }
                : message
            ),
          }
        : chat
    )
  );
};

// Adds a new message
export const addMessage = (chatId, setChats, newMessage, buttons = null) => {
  // Ensure newMessage is a string
  const message = buttons
    ? {
        text: newMessage,
        buttons: buttons,
      }
    : typeof newMessage === "string"
    ? newMessage
    : String(newMessage);

  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: [...chat.messages, message], // Create a new array with the added message
          }
        : chat
    )
  );
};

function changeBar(chatInput, setChatInput) {
  setChatInput({
    ...chatInput,
    showAddressInput: true,
  });
}

const askForLocationType = {
  text: "I would like to use my:",
  buttons: [
    { label: "Address", action: "Address" },
    { label: "City Name", action: "City Name" },
    { label: "Current Location", action: "Current Location" },
  ],
};

function locationTypeResponse(
  chatId,
  setChats,
  setChatInput,
  chatInput,
  UserChatData
) {
  if (UserChatData.action === "Current Location") {
    //Change the previous message if current location is clicked
    getCurrentLocation((latitude, longitude) => {
      changePrevious(
        chatId,
        setChats,
        `I would like to use my current location -- (${latitude}, ${longitude})`
      );
      if (UserChatData.locationType === "start") {
        UserChatData.startCoords = [latitude, longitude];
      } else {
        UserChatData.endCoords = [latitude, longitude];
      }
    });
  } else if (UserChatData.action === "Address") {
    // Handle address input logic
    changePrevious(chatId, setChats, `I would like to use my address.`);
    addMessage(
      chatId,
      setChats,
      "Sounds good! Please enter your address information."
    );

    //Change the bar to be the address bar
    changeBar(chatInput, setChatInput);
  } else if (UserChatData.action === "City Name") {
    // Handle city name input logic
    changePrevious(chatId, setChats, "I would like to use my city name.");
    addMessage(chatId, setChats, "Sounds good! Please enter your city name.");
  }
}

// Main Workflow
export const startWorkFlow = async (
  setChats,
  chatId,
  setChatInput,
  chatInput,
  UserChatData
) => {
  // Ask user for location type
  addMessage(
    chatId,
    setChats,
    askForLocationType.text,
    askForLocationType.buttons
  );

  // Wait for user to select a button
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.action) {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  locationTypeResponse(chatId, setChats, setChatInput, chatInput, UserChatData);

  // Wait for user to input something
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.submitted || UserChatData.startCoords[0] != "") {
        UserChatData.submitted = false;
        UserChatData.action = null;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Bot adds a message
  addMessage(
    chatId,
    setChats,
    "Perfect! How many stops would you like to take?"
  );

  UserChatData.showStopSlider = true;

  // Wait for user to input stops
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!UserChatData.showStopSlider) {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Ask user for end location
  addMessage(
    chatId,
    setChats,
    "How would you like to enter your end location?"
  );

  UserChatData.locationType = "end";

  addMessage(
    chatId,
    setChats,
    askForLocationType.text,
    askForLocationType.buttons
  );

  // Wait for user to select a button
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.action) {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  locationTypeResponse(chatId, setChats, setChatInput, chatInput, UserChatData);

  // Wait for user to input something
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.submitted || UserChatData.endCoords[0] != "") {
        UserChatData.submitted = false;
        UserChatData.action = null;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  addMessage(chatId, setChats, "End of workflow");
  console.log(UserChatData.startAddress);
  console.log(UserChatData.endAddress);
};
