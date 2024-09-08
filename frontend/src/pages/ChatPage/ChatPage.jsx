import React, { useState, useRef, useEffect, useContext } from "react";
import { Box, TextField, Button, Typography } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import MapButton from "../../components/buttons/MapButton";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { startWorkFlow, addMessage } from "./startWorkFlow";
import CarInputBar from "./InputCar";
import BudgetSlider from "./InputBudget";
import StopSlider from "./InputStops";
import AddressBar from "./InputAddress";
import { UserDataContext } from "../../states/UserDataContext";
import { validateLocation } from "./ValidateLocation";
import { ring } from 'ldrs' //Loading Animation
import "./ChatPage.css";

ring.register('loading-chat')  //Define the loading animation

const ChatPage = () => {

  // Retrieve the global instance of UserData and getUserData function
  const { UserData, getUserData } = useContext(UserDataContext);
  // Grab the chat logs
  const ChatLogsData = UserData.chatlogs;
  // State to track current chats data
  const [UserChatData, setUserChatData] = useState(ChatLogsData?.chatdata?.length > 0?
    ChatLogsData.getChatDataById(ChatLogsData.currentId):
    ChatLogsData.createChatData(1));

  // Initial message displayed in a new chat
  const initialMessage = [
    {
      text: "Hello there! I’m Journey Genie, and I’m excited to help you with your trip planning. To get started, could you please tell me what type of location you'd like to use?",
      sender: 'bot' // either bot or user
    },
  ];

  // State to manage the list of chats
  const [chats, setChats] = useState([]);

  // State to manage the currently selected chat
  const [selectedChat, setSelectedChat] = useState(null);

  // State to manage the chat input (message box)
  const [chatInput, setChatInput] = useState({
    name: "Type a Message",
    message: "",
  });

  // Ref to scroll the chat to the bottom
  const chatEndRef = useRef(null);
  
  // State to track workflow status
  const [workflowStarted, setWorkflowStarted] = useState(UserChatData.workflowStarted? UserChatData.workflowStarted : false);
  // Trigger workflow when a chat is selected, ensuring it only starts once
  useEffect(() => {
    setWorkflowStarted(UserChatData.workflowStarted); // ensure the accurate workflowStarted is set
    if (selectedChat && !workflowStarted && UserChatData) {
      // Start the workflow for the newly selected chat
      startWorkFlow(
        setChats,
        selectedChat.id,
        setChatInput,
        chatInput,
        UserChatData, 
        ChatLogsData,
        getUserData,
        getSavedChats,
      );
      // Mark the workflow as started
      setWorkflowStarted(true);
    }
  }, [selectedChat, workflowStarted, UserChatData]);


  // Get SavedChats from sessionStorage
  const getSavedChats = () => {
    const savedChats = sessionStorage.getItem("chats");
    if (savedChats && savedChats.length > 2) { // Check that more than an empty array is returned
      const parsedChats = JSON.parse(savedChats);
      console.log("Loaded chats from sessionStorage:", parsedChats);
      return parsedChats;
    } else {
      return null;
    };
  }

  // Automatically load chats from sessionStorage or create a chat during initial mount
  useEffect(() => {
    const prevChats = getSavedChats();
    if(prevChats){
      setChats(prevChats);
    }else{
      const initialChats = [
        {
          id: 1,
          title: "Chat 1",
          messages: initialMessage,
        },
      ];
      console.log("Initialized chats with default:", initialChats);
      setChats(initialChats);
    }
    for(var i=0; i < ChatLogsData.chatdata.length; i++){
      ChatLogsData.chatdata[i].workflowStarted = false; // Reset the workflows for all saved chats on mount
    }
  }, []);


  // Automatically setSelected chat on initial mount
  useEffect(() => {
    if (chats.length > 0) {
      const idx = chats.findIndex(chat => chat.id === UserChatData.chatId);
      if (idx >= 0 && idx < chats.length) {
        setSelectedChat(chats[idx]);
      } else {
        console.error("Invalid chat ID:", UserChatData.chatId);
      }
    }
  }, [chats, UserChatData.chatId]);


  
  // Handle chat selection from the sidebar
  const handleSelectChat = (chat) => {
    const selectedChatData = ChatLogsData.getChatDataById(chat.id);
    setSelectedChat({ ...chat, ...selectedChatData });
    setUserChatData(selectedChatData);
    ChatLogsData.currentId = chat.id;
  };


  // Scroll to the bottom of the chat when a new chat is selected
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);
  

  // Handle the sending of messages in the chat
  const handleSendMessage = async () => {
    if (selectedChat) {
      if (UserChatData.showStopSlider) {
        // Handle input of the number of user stops
        addMessage(selectedChat.id, setChats, UserChatData.stops, 'user');
        UserChatData.showStopSlider = false; // Hide the stop slider
      } else if (UserChatData.showBudgetSlider) {
        addMessage(selectedChat.id, setChats, `$${UserChatData.hotelBudget}`, 'user')  //Display the hotel budget the user input
        UserChatData.showBudgetSlider = false // Hide the budget slider
      } else if (UserChatData.action === "Car Details") { //Store the car details if action is "Car Details"
        // Handle car input message
        const carDetails = UserChatData.carDetails || ["", "", ""];
        
        addMessage(
          selectedChat.id,
          setChats,
          `${carDetails[0]} ${carDetails[1]} ${carDetails[2]}`,
          'user',
        );
        UserChatData.showInputBar = false
      } else if (UserChatData.showAddressInput) {
        // Handle address input message
        const address =
          UserChatData.locationType === "start"
            ? UserChatData.startAddress
            : UserChatData.endAddress;
        
        addMessage(
          selectedChat.id,
          setChats,
          `${address[0]} ${address[1]} ${address[2]} ${address[3]}`,
          'user',
        );
        UserChatData.showInputBar = false
        UserChatData.showAddressInput = false
        
        // Confirm the address that the user inputted
        if(UserChatData.locationType === "start"){
          UserChatData.startConfirmed = await validateLocation(`${address[0]} ${address[1]} ${address[2]} ${address[3]}`, false, UserChatData, setChats, setChatInput, chatInput);
        }
        else{
          UserChatData.endConfirmed = await validateLocation(`${address[0]} ${address[1]} ${address[2]} ${address[3]}`, false, UserChatData, setChats, setChatInput, chatInput);
        }

      } else if (chatInput.message.trim() !== "") {
        // Handle regular message submission
        addMessage(selectedChat.id, setChats, chatInput.message, 'user');

        // Store the message if action is "City Name"
        if (UserChatData.action === "City Name") {
          if (UserChatData.locationType === "start") {
            UserChatData.startAddress[1] = chatInput.message;
            UserChatData.startConfirmed = await validateLocation(UserChatData.startAddress[1], false, UserChatData, setChats, setChatInput, chatInput);
          } else if (UserChatData.locationType === "end") {
            UserChatData.endAddress[1] = chatInput.message;
            UserChatData.endConfirmed = await validateLocation(UserChatData.endAddress[1], false, UserChatData, setChats, setChatInput, chatInput);
          }
        }

        //Hide the input bar
        UserChatData.showInputBar = false

        // Reset the input field
        setChatInput({
          ...chatInput,
          message: "",
        });
      
      }

    }
  };

  // Create a ref to store the previous chatid
 const previousChatIdRef = useRef(UserChatData.chatId);

  // Effect to handle adding and removing loaders
  useEffect(() => {
    // Check if the chatid has changed
    if (UserChatData.chatId !== previousChatIdRef.current) {
      // Update the ref with the new chatid
      previousChatIdRef.current = UserChatData.chatId;
      return; // Exit early to avoid running the effect when chatid changes
    }

    // Handle loading state
    if (UserChatData.loading) {
      // Add a loading message if not already added
      addMessage(UserChatData.chatId, setChats, "loading", 'bot');
    } else {
      // Remove the loading message when loading is false
      deleteLoader();
    }
  }, [UserChatData.loading, UserChatData.chatId]);

    // Function to delete the loader message
    const deleteLoader = () => {
      setChats((prevChats) =>
        prevChats.map((chat) =>
          chat.id === UserChatData.chatId
            ? {
                ...chat,
                messages: chat.messages.filter(
                  (message) => !(message.type === 'loading-chat')
                ),
              }
            : chat
        )
      );
    };

  const handleNewChat = () => {
    const maxId = chats.reduce((max, chat) => Math.max(max, chat.id), 0);
    console.log('Chat ID:', maxId);
    const newChatId = maxId + 1;
  
    // Create new chat data
    const NewChatData = ChatLogsData.createChatData(newChatId);
  
    // Create new chat object
    const newChat = {
      id: newChatId,
      title: `Chat ${newChatId}`,
      messages: initialMessage,
    };
  
    // Update UserChatData and chats
    setUserChatData(NewChatData);
    setChats((prevChats) => [...prevChats, newChat]);
    setSelectedChat(newChat);
    setWorkflowStarted(false)
  };


  // Handle the deletion of a chat
  const handleDeleteChat = (chatId) => {
    setChats((prevChats) => prevChats.filter((chat) => chat.id !== chatId));
    ChatLogsData.removeChatData(chatId);
    if (selectedChat?.id === chatId) {
      setSelectedChat(null); // Deselect the chat if it's the one being deleted
    }
  };
  

  // Handle the pressing of the "Enter" key to send a message
  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Box className="page-container">
      {/* Sidebar for chat list and navigation */}
      <Box className="sidebar">
        <Box>
          <Button
            className="sidebar-top"
            variant="contained"
            onClick={handleNewChat}
            startIcon={<AddIcon />}
          >
            New Chat
          </Button>
        </Box>

        {/* Display list of chats in the sidebar */}
        <Box className="chat-logs">
          {chats.map((chat) => (
            <Box
              key={chat.id}
              className={`chat-item ${
                selectedChat?.id === chat.id ? "selected" : ""
              }`}
              onClick={() => handleSelectChat(chat)}
              sx={{
                bgcolor:
                  selectedChat?.id === chat.id
                    ? customTheme.palette.white.dark
                    : customTheme.palette.white.main,
                color: selectedChat?.id === chat.id ? "white" : "text.primary",
              }}
            >
              <Typography variant="body2">{chat.title}</Typography>
              <Box className="close-icon-wrapper">
                <CloseIcon
                  className="close-icon"
                  onClick={(e) => {
                    e.stopPropagation(); // Prevent chat selection on close icon click
                    handleDeleteChat(chat.id);
                  }}
                />
              </Box>
            </Box>
          ))}
        </Box>

        {/* Sidebar bottom buttons for map and itinerary */}
        <Box className="sidebar-bottom">
          <Box sx={{ mb: -1, width: "100%" }}>
            <MapButton route={UserChatData.route}/>
          </Box>
          <Box sx={{ mb: -1, width: "100%" }}>
            <ItineraryButton itinerary={UserChatData.itinerary} />
          </Box>
          <LogoButton />
        </Box>
      </Box>

      {/* Main content area displaying the chat messages */}
      <Box className="main-content">
        {/* Header with app title */}
        <Box className="header">
          <Typography variant="h6" color="white">
            Journey Genie
          </Typography>
        </Box>

        {/* Chat box area */}
        <Box className="chat-box">
          {selectedChat ? (
            <Box className="chat-messages">
              {/* Display messages in the selected chat */}
              {selectedChat.messages.map((message, index) => {
                if (Object.keys(message).length === 2) {
                  // Render simple text messages
                  return (
                    <Box
                      key={index}
                      className={`message ${message.sender}`}
                    >
                      <Typography variant="body1">{message.text}</Typography>
                    </Box>
                  );
                }
                else if (message.buttons) {
                  // Render messages that contain both text and buttons
                  return (
                    <Box key={index} className="message-container user">
                      {/* Render the message text */}
                      <Box className="message user">
                        <Typography variant="body1">{message.text}</Typography>
                      </Box>
                      {/* Render buttons associated with the message */}
                      <Box className="button-container">
                        {message.buttons.map((button, buttonIndex) => (
                          <Button
                            key={buttonIndex}
                            className="chat-buttons"
                            variant="contained"
                            color="primary"
                            onClick={() => (UserChatData.action = button.action)}
                          >
                            {button.label}
                          </Button>
                        ))}
                      </Box>
                    </Box>
                  );
                }  else if (UserChatData.loading) {
                  // Render a React component if 'message' is a React element
                  return (
                    <Box key={index} className="message-container">
                      {/* Dynamically create and render the React component */}
                      <loading-chat size="30" color="black"></loading-chat>
                    </Box>
                  );
                }
                // Return null if none of the above conditions are met
                return null;
              })}
              <div ref={chatEndRef} /> {/* Scroll to bottom */}
            </Box>
          ) : (
            <Typography variant="body1">Select a chat to start</Typography>
          )}
        </Box>

        {/* Input area for typing and sending messages */}
        {UserChatData.showInputBar ? (
        <Box className="input-area">
          {UserChatData.showAddressInput ? (
            <AddressBar UserChatData = {UserChatData} handleKeyDown={handleKeyDown}/> // Show AddressBar if address input is required
          ) : UserChatData.showStopSlider ? (
            <StopSlider UserChatData = {UserChatData} handleKeyDown={handleKeyDown}/> // Show StopSlider if stop input is required
          ) : UserChatData.showBudgetSlider ? (
            <BudgetSlider UserChatData = {UserChatData} handleKeyDown={handleKeyDown}/>// Show BudgetSlider if budget input is required
          ) : UserChatData.action === "Car Details" ? (
            <CarInputBar UserChatData = {UserChatData} handleKeyDown={handleKeyDown}/> // Show Car Input Bar if car input is required
          ) : (
            <TextField
              label={chatInput.name}
              placeholder={chatInput.name}
              value={chatInput.message}
              onChange={(e) =>
                setChatInput({ ...chatInput, message: e.target.value })
              }
              onKeyDown={handleKeyDown}
              fullWidth
              multiline
              sx={{
                backgroundColor: customTheme.palette.white.main,
                borderRadius: "5px",
              }}
            />
          )}
          <Button
            variant="contained"
            color="primary"
            className="send-button"
            onClick={handleSendMessage}
            disabled={!UserChatData.route && UserChatData.budget > 0} // Disable the send button if the initial route 
          >
            Send
          </Button>
        </Box>
        ):(
        <Box className = "input-area"/>
        )}
      </Box>
    </Box>
  );
};

export default ChatPage;
