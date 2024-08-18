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
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: [...chat.messages, newMessage], // Create a new array with the added message
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

// Main Function

export const startWorkFlow = (
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

    // Bot adds a message
    addMessage(
      chatId,
      "Perfect! How many stops would you like to take?",
      setChats
    );
  } else if (action === "Address") {
    //Change the previous message if address is clicked
    changePrevious(chatId, setChats, `I would like to use my address.`);

    // Bot adds a message
    addMessage(
      chatId,
      "Sounds good! Please enter your address information.",
      setChats
    );

    changeBar(chatInput, setChatInput);
  } else if (action === "City Name") {
    //Change the previous message  if city name is clicked
    changePrevious(chatId, setChats, "I would like to use my city name.");

    // Bot adds a message
    addMessage(chatId, "Sounds good! Please enter your city name.", setChats);
  }
};
