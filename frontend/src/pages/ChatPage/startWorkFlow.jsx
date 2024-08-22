import { validateLocation } from "./ValidateLocation";
import { useEffect } from "react"
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



// Updates the previous message with a new one based on the user's input
const changePrevious = (chatId, setChats, newMessage) => {
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: (chat.messages || []).map((message) =>
              typeof message === "object" &&
              (message.text === "I would like to use:" || message.text ==="The address is:")
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

const askForConfirmation = {
  text: "The address is:",
  buttons: [
    {label: "Correct", action: "Correct"},
    {label: "Incorrect", action: "Incorrect"}
  ]
}

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
    getCurrentLocation(async (latitude, longitude) => {
      // Update the previous message to include the location coordinates
      changePrevious(chatId, setChats, `I would like to use: Current Location`);
      // Save the coordinates to UserChatData
      if (UserChatData.locationType === "start") {
        UserChatData.startCoords = [latitude, longitude];
        UserChatData.startConfirmed = await validateLocation([latitude, longitude], true, UserChatData, setChats, setChatInput, chatInput);
      } else {
        UserChatData.endCoords = [latitude, longitude];
        UserChatData.endConfirmed = await validateLocation([latitude, longitude], true, UserChatData, setChats, setChatInput, chatInput);
      }
    });
  } else if (UserChatData.action === "Address") {
    // Allow user access to the input bar
    UserChatData.showInputBar = true
    UserChatData.showAddressInput = true
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
    // Allow user access to the input bar
    UserChatData.showInputBar = true
    // If the user chose 'City Name'
    changePrevious(chatId, setChats, "I would like to use: City Name");
    addMessage(chatId, setChats, "Sounds good! Please enter your city name.");
  }
}

// Workflow for allowing a user to input a location 
export async function inputLocationWorkflow(chatId,
  setChats,
  setChatInput,
  chatInput,
  UserChatData
){

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
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });
  // Handle the user's selected location type
  locationTypeResponse(chatId, setChats, setChatInput, chatInput, UserChatData);

  // Wait for the user to submit the location data
  if(UserChatData.locationType === "end"){
    await new Promise((resolve) => {
      const interval = setInterval(() => {
        if (UserChatData.endConfirmed) {
          UserChatData.action = null;
          clearInterval(interval);
          resolve();
        }
      }, 100);
    });
  }
  
  else{
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (UserChatData.startConfirmed) {
        UserChatData.action = null;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });
}}



// Displays the backend address to user and asks for the confirmation
async function displayConfirmationDetails(chatId,
  setChats,
  UserChatData,){
    const address = UserChatData.endConfirmed? UserChatData.endConfirmed : UserChatData.startConfirmed;

    // Display address from backend
    addMessage(
      chatId,
      setChats,
      `Is this the correct address? ${address}`,
    );
  
    // Ask for user to confirm the backend address
    addMessage(
      chatId,
      setChats,
      askForConfirmation.text,
      askForConfirmation.buttons,
    );
  
    // Wait for user to confirm the address
    await new Promise((resolve) => {
      const interval = setInterval(() => {
        if (UserChatData.action) {
          clearInterval(interval);
          resolve();
        }
      }, 100);
    });
    changePrevious(chatId, setChats, `The address is: ${UserChatData.action}`);
}

// Loops confirmation of location until it is successfully validated
async function handleConfirmation(
  chatId,
  setChats,
  setChatInput,
  chatInput,
  UserChatData,
){

  await displayConfirmationDetails(chatId, setChats, UserChatData);
  
  // Loop until the user sends a correct response
  while(UserChatData.action !== "Correct"){
    UserChatData.action = null;
    if(UserChatData.endConfirmed){
      UserChatData.endConfirmed = null;
    }
    else{UserChatData.startConfirmed = null;}
    // Message prompting re-entry of address
    addMessage(
      chatId,
      setChats,
      "My apologies, how would you like to re-enter the location?"
    );
    // Have them repeat inputting their location
    await inputLocationWorkflow(chatId, setChats, setChatInput, chatInput, UserChatData);
    // Have the user confirmed the newly generated address
    await displayConfirmationDetails(chatId, setChats, UserChatData);
  }
  UserChatData.action = null;
}
// Create a function that can handle rollbacks
const rollbackToCheckpoint = (checkpoint, setChatInput) => {
  // Restore the UserChatData state
  Object.assign(UserChatData, checkpoint);

  // Restore the chatInput state
  setChatInput({ ...checkpoint.chatInput });

};


// Main Workflow
// This function orchestrates the chat flow, asking for and processing user inputs
export const startWorkFlow = async (
  setChats,
  chatId,
  setChatInput,
  chatInput,
  UserChatData
) => {
    // Save initial state as a checkpoint
    const initialState = {
      ...UserChatData,
      chatInput: { ...chatInput },
    };

  UserChatData.workflowStarted = true
  UserChatData.showInputBar = false
  // Ask for the starting location preferences
  await inputLocationWorkflow(chatId,
    setChats,
    setChatInput,
    chatInput,
    UserChatData);

  // Confirm the users starting address with the backend
  await handleConfirmation(
    chatId,
    setChats,
    setChatInput,
    chatInput,
    UserChatData,
  );

  // Ask how many stops the user wants to take
  addMessage(
    chatId,
    setChats,
    "Perfect! How many stops would you like to take?"
  );

  // Show a slider for the user to select the number of stops
  UserChatData.showInputBar = true;
  UserChatData.showStopSlider = true;

  // Wait for the user to submit the number of stops
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!UserChatData.showStopSlider) {
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });
  UserChatData.showInputBar = false;

  // Ask for the end location
  addMessage(
    chatId,
    setChats,
    "How would you like to enter your end location?"
  );

  // Change the location type to 'end'
  UserChatData.locationType = "end";


  // Ask for ending location preferences
  await inputLocationWorkflow(chatId,
    setChats,
    setChatInput,
    chatInput,
    UserChatData);

  
  // Confirm the users ending address with the backend
  await handleConfirmation(
    chatId,
    setChats,
    setChatInput,
    chatInput,
    UserChatData,
  );
  
  // End the workflow with a message
  addMessage(chatId, setChats, "End of workflow");

};
