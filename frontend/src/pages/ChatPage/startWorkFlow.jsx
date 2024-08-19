// Helper Function

// Function that gets the user's current location
// It takes a callback function as an argument, which is called with the latitude and longitude once the location is obtained.
const getCurrentLocation = (callback) => {
  if (navigator.geolocation) {
    // If the browser supports geolocation, get the current position
    navigator.geolocation.getCurrentPosition(
      (position) => {
        // Call the callback with the latitude and longitude
        callback(position.coords.latitude, position.coords.longitude);
      },
      (error) => {
        // Log an error if there is an issue getting the location
        console.error("Error getting location:", error);
      }
    );
  } else {
    // Log an error if geolocation is not supported by the browser
    console.error("Geolocation is not supported by this browser.");
  }
};

// Sends an API request to our backend to validate the location
// It takes a starting location and a flag indicating whether the location is a coordinate or an address
const validateLocation = async (start, isCoordinate = false) => {
  try {
    // Construct the query parameter based on whether the input is a coordinate or an address
    const queryParam = isCoordinate
      ? `coordinates=${encodeURIComponent(start)}`
      : `address=${encodeURIComponent(start)}`;

    // Send the request to the server
    const response = await fetch(`/validate-location?${queryParam}`);

    // Check if the response is ok
    if (!response.ok) {
      throw new Error("Network response was not ok");
    }

    // Parse the response as text
    const location = await response.text();
    console.log("Validated Location:", location);

    // Return the location data
    return location;
  } catch (error) {
    // Log any errors encountered during the request
    console.error("Error validating location:", error);
  }
};

// Updates the previous message with a new one based on the user's input
const changePrevious = (chatId, setChats, newMessage) => {
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: (chat.messages || []).map((message) =>
              typeof message === "object" &&
              message.text === "I would like to use:"
                ? {
                    ...message,
                    text: newMessage,
                    buttons: [], // Remove buttons after the choice is made
                  }
                : message
            ),
          }
        : chat
    )
  );
};

// Adds a new message to the chat with optional buttons
export const addMessage = (chatId, setChats, newMessage, buttons = null) => {
  // Ensure the newMessage is a string, optionally with buttons
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
            messages: [...chat.messages, message], // Append the new message to the chat
          }
        : chat
    )
  );
};

// Changes the input bar to show the address input field
function changeBar(chatInput, setChatInput) {
  setChatInput({
    ...chatInput,
    showAddressInput: true, // Show the address input field
  });
}

// Predefined object representing the location type options presented to the user
const askForLocationType = {
  text: "I would like to use:",
  buttons: [
    { label: "Address", action: "Address" },
    { label: "City Name", action: "City Name" },
    { label: "Current Location", action: "Current Location" },
  ],
};

// Handles the user's response based on their chosen location type
function locationTypeResponse(
  chatId,
  setChats,
  setChatInput,
  chatInput,
  UserChatData
) {
  if (UserChatData.action === "Current Location") {
    // If the user chose 'Current Location'
    getCurrentLocation((latitude, longitude) => {
      // Update the previous message to include the location coordinates
      changePrevious(chatId, setChats, `I would like to use: Current Location`);
      // Save the coordinates to UserChatData
      if (UserChatData.locationType === "start") {
        UserChatData.startCoords = [latitude, longitude];
      } else {
        UserChatData.endCoords = [latitude, longitude];
      }
    });
  } else if (UserChatData.action === "Address") {
    // If the user chose 'Address'
    changePrevious(chatId, setChats, `I would like to use: Address`);
    addMessage(
      chatId,
      setChats,
      "Sounds good! Please enter your address information."
    );

    // Change the input bar to show the address input field
    changeBar(chatInput, setChatInput);
  } else if (UserChatData.action === "City Name") {
    // If the user chose 'City Name'
    changePrevious(chatId, setChats, "I would like to use: City Name");
    addMessage(chatId, setChats, "Sounds good! Please enter your city name.");
  }
}

// Main Workflow
// This function orchestrates the chat flow, asking for and processing user inputs
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

  // Wait for the user to select a location type
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.action) {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Handle the user's selected location type
  locationTypeResponse(chatId, setChats, setChatInput, chatInput, UserChatData);

  // Wait for the user to submit the location data
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

  // Ask how many stops the user wants to take
  addMessage(
    chatId,
    setChats,
    "Perfect! How many stops would you like to take?"
  );

  // Show a slider for the user to select the number of stops
  UserChatData.showStopSlider = true;

  // Wait for the user to submit the number of stops
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!UserChatData.showStopSlider) {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Ask for the end location
  addMessage(
    chatId,
    setChats,
    "How would you like to enter your end location?"
  );

  // Change the location type to 'end'
  UserChatData.locationType = "end";

  // Ask user for the end location type
  addMessage(
    chatId,
    setChats,
    askForLocationType.text,
    askForLocationType.buttons
  );

  // Wait for the user to select the end location type
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.action) {
        UserChatData.submitted = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  // Handle the user's selected end location type
  locationTypeResponse(chatId, setChats, setChatInput, chatInput, UserChatData);

  // Wait for the user to submit the end location data
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

  // End the workflow with a message
  addMessage(chatId, setChats, "End of workflow");

  // Log the start and end addresses (or coordinates)
  console.log(UserChatData.startAddress);
  console.log(UserChatData.endAddress);
};
