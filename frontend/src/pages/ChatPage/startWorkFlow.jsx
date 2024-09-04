import { validateLocation } from "./ValidateLocation";
import { getInitialRoute, getFinalRoute } from "./getRoute";
import { generateItinerary } from "../ItineraryPage/generateItinerary";
import { calcHotelBudget } from "./CalcBudget"
import { Data, ChatLogs } from "../../states/UserDataContext";
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
export const addMessage = (chatId, setChats, newMessage, buttons = null) => {
  // Ensure the newMessage is a string, optionally with buttons
  const message = newMessage === "loading" 
    ? <loading-chat size="30" color="black"></loading-chat>
    : buttons
    ? {
        text: newMessage,
        buttons: buttons,
      }
    : typeof newMessage === "string"
    ? newMessage
    : String(newMessage);

  setChats((prevChats) =>{
    const idx = prevChats.findIndex(chat => chat.id === chatId); // get index of current chat
    const prevLength = prevChats[idx]?.messages?.length-1;
    const prevMessage = prevChats[idx]?.messages[prevLength];
    if( prevMessage !== message && // Check if they are the same text
      !(typeof prevMessage === 'object' && typeof message === 'object' && prevMessage.text === message.text) // Check if they are the same objects
    ){ // Determine if the last message is the same as the previous
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

// Function to save all relevant User information to the sessionStorage
const saveUserData = (setChats, UserChatData, getUserData, getSavedChats) => {
  setChats((chats) =>{
    if(chats.length> 0){ // Make sure data's valid and save condition is true
      // Save current chat to the previous chats in the sessionStorage
      var newChats = null; // Variable for chats to be saved
      const prevChats = getSavedChats(); // Get the sessionStorage chats
      const newChat = chats.find(Chat => // Find the currently selected chat in chats
        Chat.id === UserChatData.chatId
      );
      if(prevChats && newChat){
        // If the current chatId already exists in the sessionStorage
        if(prevChats.find(
          Chat => Chat.id === UserChatData.chatId
        )){ // replace the sessionStorage version with the new chat
          newChats = prevChats.map(Chat =>
            Chat.id === UserChatData.chatId? newChat: Chat
          );
        }else{ // Add the new chat if it's the first instance
          prevChats.push(newChat);
          newChats = prevChats;
        };
      }else{
        // save the first session version of chats
        newChats = chats
      };
      
      sessionStorage.setItem("chats", JSON.stringify(newChats));
      console.log("Saved chats to sessionStorage:", newChats);
      

      // Save new UserChatData to previously stored UserChatData in sessionStorage
      var saveData = null;
      const prevData = getUserData(); // Retrieve previous value of UserData
      console.log("Previous Data in storage", prevData);
      if(prevData?.chatlogs?.chatdata?.length > 0){ // Check to be sure it isn't the first instance of the data
        if(
          prevData.chatlogs.getChatDataById(UserChatData.chatId) // Check if the ChatData already exists
        ){
          const newChatLogs = prevData.chatlogs.chatdata.map(ChatData => // Map the new UserData to replace the previous one
            ChatData.chatId === UserChatData.chatId? UserChatData : ChatData);
          prevData.chatlogs.chatdata = newChatLogs; // set the previous User Data to include the new UserChatData
        }else{
          prevData.chatlogs.addChatData(UserChatData); // add the new Chat Data
        }
        prevData.chatlogs.currentId = UserChatData.chatId; // Set the currentId to be the current Chat Datas
        saveData = prevData;
      }else{ // If no valid data is stored create some with UserChatData
        const first_log = new ChatLogs([UserChatData], UserChatData.chatId) // Create the first ChatLogs
        saveData = new Data(first_log) // Create the first data instance with the current UserChatData
      };
      
      console.log("Saved data to sessionStorage: ", saveData);
      // Save the current ChatData to the session storage
      sessionStorage.setItem(
        "UserData",
        JSON.stringify({
          chatlogs: {
            chatdata: saveData.chatlogs.chatdata,
            currentId: saveData.chatlogs.currentId,
          },
        })
      );
    };
    return chats
  })
};

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
    );

    // Change the input bar to show the address input field
    changeBar(chatInput, setChatInput);
  } else if (UserChatData.action === "City Name") {
    // Allow user access to the input bar
    UserChatData.showInputBar = true
    // If the user chose 'City Name'
    replacePreviousMessage(chatId, setChats, "I would like to use: City Name");
    addMessage(chatId, setChats, "Sounds good! Please enter your city name.");
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
    replacePreviousMessage(chatId, setChats, `The address is: ${UserChatData.action}`);
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
  getUserData,
  getSavedChats,
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
      "Perfect! How many stops would you like to take?",
    );

    // Show a slider for the user to select the number of stops
    UserChatData.showInputBar = true;
    UserChatData.showStopSlider = true;

    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
    
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

    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };

  if (!UserChatData.endConfirmed && !UserChatData.initial){  // Checkpoint 3: Choose an end location
    // Ask for the end location
    addMessage(
      chatId,
      setChats,
      "How would you like to enter your end location?",
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
      UserChatData.stops,
      UserChatData
    );

    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };

  UserChatData.hotelBudget = await calcHotelBudget(UserChatData.initial['duration']); // Get the estimated minimum hotel budget
  if(UserChatData.initial){ // Checkpoint 4: Calculate a budget
    if (UserChatData.hotelBudget) {  //If the user has to go to a hotel
      addMessage(chatId, setChats, `We estimate your minimum hotel cost to be $${UserChatData.hotelBudget}. Would you like to increase this budget?`)
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
  
    UserChatData.carBudget = 10
    // Calculate the total budget
    UserChatData.budget  = UserChatData.hotelBudget + UserChatData.carBudget

    addMessage(chatId, setChats, `In total, we estimate your budget to be $${UserChatData.budget}:\nHotel Budget: $${UserChatData.hotelBudget}\nGas Budget: $${UserChatData.carBudget}`)

    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };


  if(!UserChatData.route && UserChatData.initial){ // Checkpoint 5: Generate the final route
    // Final Route Checkpoint
    // Generate the final route account for budget
    UserChatData.route = await getFinalRoute(UserChatData.initial,
      UserChatData.budget,
      UserChatData.stops
    );
    
    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };

  if(UserChatData.route && !UserChatData.itinerary){ // Checkpoint 6: End behaviors
    // Generate the itinerary data 
    UserChatData.itinerary = await generateItinerary(UserChatData.route);
    ChatLogsData.chatdata[UserChatData.chatId-1] = UserChatData; // save the current chat data to the ChatLogs at end of workflow

    // End the workflow with a message
    addMessage(chatId, setChats, "Successfully generated your trip! Click on the Map and Itinerary buttons to view the details.",);
    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  }
  else if (!UserChatData.route){
    // Send a message prompting the user to resend their information
    addMessage(UserChatData.chatId, setChats, "Error creating route. Please re-enter how you would like to choose your starting location.",);

    // Reset values 
    UserChatData.action = null;
    UserChatData.locationType = 'start';
    UserChatData.endConfirmed = null;
    UserChatData.startConfirmed = null;
    UserChatData.initial = null;

    // Restart workflow for another route
    await startWorkFlow(setChats,
        UserChatData.chatId,
        setChatInput,
        chatInput,
        UserChatData,
        ChatLogsData,
        getUserData,
        getSavedChats,
    );
    saveUserData(setChats, UserChatData, getUserData, getSavedChats);
  };
};
