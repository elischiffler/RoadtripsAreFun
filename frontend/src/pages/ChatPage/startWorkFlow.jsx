import { UserChatDataContext } from "../../states/UserChatDataContext";
import { useContext } from "react";
// Helper Functions

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
export const addMessage = (chatId, newMessage, setChats) => {
  // Ensure newMessage is a string
  const message =
    typeof newMessage === "string" ? newMessage : String(newMessage);

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

const waitForCondition = (conditionFn, intervalTime = 100) => {
  return new Promise((resolve) => {
    const interval = setInterval(() => {
      if (conditionFn()) {
        clearInterval(interval);
        resolve();
      }
    }, intervalTime);
  });
};

// Main Workflow
export const startWorkFlow = async (
  setChats,
  chatId,
  action,
  setChatInput,
  chatInput,
  UserChatData
) => {
  if (action === "Current Location") {
    //Change the previous message if current location is clicked
    getCurrentLocation((latitude, longitude) => {
      changePrevious(
        chatId,
        setChats,
        `I would like to use my current location -- (${latitude}, ${longitude})`
      );
      UserChatData.coords = [latitude, longitude];
    });
  } else if (action === "Address") {
    // Handle address input logic
    changePrevious(chatId, setChats, `I would like to use my address.`);
    addMessage(
      chatId,
      "Sounds good! Please enter your address information.",
      setChats
    );

    //Change the bar to be the address bar
    changeBar(chatInput, setChatInput);
  } else if (action === "City Name") {
    // Handle city name input logic
    changePrevious(chatId, setChats, "I would like to use my city name.");
    addMessage(chatId, "Sounds good! Please enter your city name.", setChats);
  }

  // Wait for user to input something
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.submitted || UserChatData.coords[0] != "") {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Bot adds a message
  addMessage(
    chatId,
    "Perfect! How many stops would you like to take?",
    setChats
  );

  UserChatData.showStopSlider = true;

  // Wait for user to input stops
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!UserChatData.showStopSlider) {
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Ask user for end location
  addMessage(
    chatId,
    "How would you like to enter your end location?",
    setChats
  );
};
