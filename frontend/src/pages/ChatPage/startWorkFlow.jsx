import { validateLocation } from "./ValidateLocation";
import { getInitialRoute, getFinalRoute } from "./getRoute";
import { generateItinerary } from "../ItineraryPage/generateItinerary";
import { calcHotelBudget, calcGasBudget } from "./CalcBudget"
import { Data, ChatLogs } from "../../states/UserDataContext";
import { updateUserData } from "./DatabaseUtils";
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



// Updates the previous message with a new one based on a dynamic match condition
const replacePreviousMessage = (chatId, setChats, newMessage) => {
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: (chat.messages || []).map((message, index, array) =>
              index === array.length - 1 // Target the last message in the array
                ? {
                    ...message,
                    text: newMessage, // Replace the text with the new message
                    buttons: [], // Optionally clear buttons
                  }
                : message
            ),
          }
        : chat
    )
  );
};

// Adds a new message to the chat with optional buttons
export const addMessage = (chatId, setChats, newMessage, sender, buttons = null) => {
  // Ensure the newMessage is a string, optionally with buttons
  const message = newMessage === "loading" 
    ? <loading-chat size="30" color="black"></loading-chat>
    : buttons
    ? {
        text: newMessage,
        sender: sender,
        buttons: buttons,
      }
    : typeof newMessage === "string"
    ? {
      text: newMessage,
      sender: sender,
      }
    : {
        text: String(newMessage),
        sender: sender,
      };

  setChats((prevChats) =>{
    const idx = prevChats.findIndex(chat => chat.id === chatId); // get index of current chat
    const prevLength = prevChats[idx]?.messages?.length-1;
    const prevMessage = prevChats[idx]?.messages[prevLength];
    if( prevMessage.text !== message.text){ // Determine if the last message is the same as the previous
      const newChats = prevChats.map((chat) => // Create a new chats with the newMessage at the end
        chat.id === chatId
          ? {
              ...chat,
              messages: [...chat.messages, message], // Append the new message to the chat
            }
          : chat
      );
      return newChats
    };
    return prevChats
  }
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
  UserChatData,
) {
  if (UserChatData.action === "Current Location") {
    UserChatData.loading = true
    // If the user chose 'Current Location'
    getCurrentLocation(async (latitude, longitude) => {
      // Update the previous message to include the location coordinates
      replacePreviousMessage(chatId, setChats, `I would like to use: Current Location`);
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
    replacePreviousMessage(chatId, setChats, `I would like to use: Address`);
    addMessage(
      chatId,
      setChats,
      "Sounds good! Please enter your address information.",
      'bot',
    );

    // Change the input bar to show the address input field
    changeBar(chatInput, setChatInput);
  } else if (UserChatData.action === "City Name") {
    // Allow user access to the input bar
    UserChatData.showInputBar = true
    // If the user chose 'City Name'
    replacePreviousMessage(chatId, setChats, "I would like to use: City Name");
    addMessage(chatId, setChats, "Sounds good! Please enter your city name.", 'bot');
  }
}

// Workflow for allowing a user to input a location 
export async function inputLocationWorkflow(chatId,
  setChats,
  setChatInput,
  chatInput,
  UserChatData,
){

  if(!UserChatData.action){
    // Ask user for location type
    addMessage(
      chatId,
      setChats,
      askForLocationType.text,
      'user',
      askForLocationType.buttons,
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
  };

  
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
  UserChatData,
){
    const address = UserChatData.endConfirmed? UserChatData.endConfirmed['address'] : UserChatData.startConfirmed['address'];

    // Display address from backend
    addMessage(
      chatId,
      setChats,
      `Is this the correct address? ${address}`,
      'bot',
    );
  
    // Ask for user to confirm the backend address
    addMessage(
      chatId,
      setChats,
      askForConfirmation.text,
      'user',
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
    replacePreviousMessage(chatId, setChats, `The address is: ${UserChatData.action}`);
}

export async function handlePromptCarInfo(
  chatId,
  setChats,
  UserChatData
){
  addMessage(chatId, setChats, "The next step in creating your budget is getting an estimated gas cost. Please enter the year, make and model of the vehicle you plan to use. (e.g. 2020 Mazda CX-3)", 'bot',);
  UserChatData.action = "Car Details";
  UserChatData.showInputBar = true;

  // Wait for the user to input there car details
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!UserChatData.showInputBar) {
        UserChatData.action = null
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  UserChatData = await calcGasBudget(UserChatData.initial['distance'], UserChatData.carDetails[0], UserChatData.carDetails[1], UserChatData.carDetails[2], UserChatData.chatId, setChats, UserChatData);
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
      "My apologies, how would you like to re-enter the location?",
      'bot',
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
  UserChatData,
  ChatLogsData,
  chatsRef,
 // getUserData,
 // getSavedChats,
  access_token
) => {
    // Save initial state as a checkpoint
    const initialState = {
      ...UserChatData,
      chatInput: { ...chatInput },
    };
  
  console.log("Starting a workflow");
  UserChatData.workflowStarted = true
  if(!UserChatData.showStopSlider && !UserChatData.startConfirmed) { // Checkpoint 1: Choose a start location
    UserChatData.showInputBar = false


    // Ask for the starting location preferences
    await inputLocationWorkflow(chatId,
      setChats,
      setChatInput,
      chatInput,
      UserChatData
    );
  

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
      "Perfect! How many attractions would you like to see?",
      'bot',
    );

    // Show a slider for the user to select the number of stops
    UserChatData.showInputBar = true;
    UserChatData.showStopSlider = true;

    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
    
  };

  if(UserChatData.showInputBar && UserChatData.showStopSlider) { // Checkpoint 2: Input stops
    if(UserChatData.showStopSlider){
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
    };

    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };

  if (!UserChatData.endConfirmed && !UserChatData.initial){  // Checkpoint 3: Choose an end location
    // Ask for the end location
    addMessage(
      chatId,
      setChats,
      "How would you like to enter your end location?",
      'bot',
    );

    UserChatData.locationType = "end";

    // Ask for ending location preferences
    await inputLocationWorkflow(chatId,
      setChats,
      setChatInput,
      chatInput,
      UserChatData,
    );

    // Confirm the users ending address with the backend
    await handleConfirmation(
      chatId,
      setChats,
      setChatInput,
      chatInput,
      UserChatData,
    );
    


    //Get the users initial route duration
    UserChatData.initial  = await getInitialRoute(UserChatData.startConfirmed['latitude'],
      UserChatData.startConfirmed['longitude'],
      UserChatData.endConfirmed['latitude'],
      UserChatData.endConfirmed['longitude'],
    );

    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };

  if(UserChatData.initial && !UserChatData.route){ // Checkpoint 4: Calculate a budget
    UserChatData.hotelBudget = await calcHotelBudget(UserChatData.initial['duration'], UserChatData.stops); // Get the estimated minimum hotel budget
    if (UserChatData.hotelBudget) {  //If the user has to go to a hotel
      addMessage(chatId, setChats, `We estimate your minimum hotel cost to be $${UserChatData.hotelBudget}. Would you like to increase this budget?`, 'bot')
      UserChatData.showInputBar = true
      UserChatData.showBudgetSlider = true // Allow user to customize their budget preference

      // Wait for the user to input there hotel budget
      await new Promise((resolve) => {
        const interval = setInterval(() => {
          if (!UserChatData.showBudgetSlider) {
            clearInterval(interval);
            resolve();
          }
        }, 100);
      });

      console.log(`hotel budget: ${UserChatData.hotelBudget}`)
    }

    // Handle getting the car info from the user and estimating a gas budget
    await handlePromptCarInfo(chatId, setChats, UserChatData); 

    // Calculate the total budget
    UserChatData.budget  = UserChatData.hotelBudget + UserChatData.carBudget

    addMessage(chatId, setChats, `In total, we estimate your budget to be $${UserChatData.budget}:\nHotel Budget: $${UserChatData.hotelBudget}\nGas Budget: $${UserChatData.carBudget}`, 'bot',)

    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };


  if(!UserChatData.route && UserChatData.initial){ // Checkpoint 5: Generate the final route
    // Final Route Checkpoint
    // Generate the final route account for budget
    UserChatData.route = await getFinalRoute(UserChatData.initial,
      UserChatData.hotelBudget,
      UserChatData.stops
    );
    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };

  if(UserChatData.route && !UserChatData.itinerary){ // Checkpoint 6: End behaviors
    // Generate the itinerary data 
    UserChatData.itinerary = await generateItinerary(UserChatData.route);
    ChatLogsData.chatdata[UserChatData.chatId-1] = UserChatData; // save the current chat data to the ChatLogs at end of workflow

    // End the workflow with a message
    addMessage(chatId, setChats, `Successfully generated your trip! Based on hotel and gas it should cost $${UserChatData.route['cost'] + UserChatData.carBudget}. Click on the Map and Itinerary buttons to view the details.`, 'bot');
    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  }
  else if (!UserChatData.route){
    // Send a message prompting the user to resend their information
    addMessage(UserChatData.chatId, setChats, "Error creating route. Please re-enter how you would like to choose your starting location.", 'bot');

    // Reset values 
    UserChatData.action = null;
    UserChatData.locationType = 'start';
    UserChatData.endConfirmed = null;
    UserChatData.startConfirmed = null;
    UserChatData.initial = null;
    UserChatData.budget = null;

    // Restart workflow for another route
    await startWorkFlow(setChats,
        UserChatData.chatId,
        setChatInput,
        chatInput,
        UserChatData,
        ChatLogsData,
        getUserData,
        getSavedChats,
        access_token,
    );
    await updateUserData(access_token, UserChatData, chatsRef.current);
    //saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };
};
