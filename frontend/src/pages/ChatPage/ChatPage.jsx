import React, { useState, useRef, useEffect, useContext } from "react";
import { Box, TextField, Button, Typography } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import MapButton from "../../components/buttons/MapButton";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import axios from 'axios';
import { startWorkFlow, addMessage } from "./startWorkFlow";
import StopSlider from "./InputStops";
import AddressBar from "./InputAddress";
import { UserDataContext } from "../../states/UserDataContext";
import "./ChatPage.css";

const ChatPage = () => {
  // Retrieve the global instance of UserData
  const UserData = useContext(UserDataContext);
  // Use the UserChatData
  const UserChatData = UserData.chat;

  // Initial message displayed in a new chat
  const initialMessage = [
    "Hello there! I’m Journey Genie, and I’m excited to help you with your trip planning. To get started, could you please tell me what type of location you'd like to use?",
  ];

  // State to manage the list of chats
  const [chats, setChats] = useState([
    {
      id: 1,
      title: "Chat 1",
      messages: initialMessage,
    },
  ]);

  // State to manage the currently selected chat
  const [selectedChat, setSelectedChat] = useState(null);

  // State to manage the chat input (message box)
  const [chatInput, setChatInput] = useState({
    name: "Type a Message",
    message: "",
    showAddressInput: false,
  });

  // Ref to scroll the chat to the bottom
  const chatEndRef = useRef(null);

  // Trigger workflow when a chat is selected, ensuring it only starts once
  useEffect(() => {
    if (selectedChat && !UserChatData.workflowStarted) {
      // Start the workflow for the newly selected chat
      startWorkFlow(
        setChats,
        selectedChat.id,
        setChatInput,
        chatInput,
        UserChatData
      );

      // Mark the workflow as started
      UserChatData.workflowStarted = true;
    }
  }, [selectedChat, UserChatData.workflowStarted]);

  // Select the first chat by default when chats are loaded
  useEffect(() => {
    if (chats.length > 0) {
      setSelectedChat(chats[0]);
    }
  }, [chats]);

  // Handle chat selection from the sidebar
  const handleAddChat = (chat) => {
    setSelectedChat(chat);
    UserChatData.workflowStarted = false;
  };

  // Scroll to the bottom of the chat when a new chat is selected
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);
  
  // Sends an API request to our backend to validate the location
  // It takes a starting location and a flag indicating whether the location is a coordinate or an address
  const validateLocation = async (input, isCoordinate) => {
    try {
      // Construct the query parameter based on whether the input is a coordinate or an address
      const data = isCoordinate
        ? {'location': {'coordinates': input}, is_coordinates: isCoordinate}
        : {'location' : {'address' : input}, is_coordinates: isCoordinate};
      
      console.log("With data:", data);

      // Send the a post request to the backend server
      const response = await axios.post(`http://localhost:8000/validate-location`, data);

      // Get the exact address as a string
      const location =  response.data;
      console.log("Validated Location:", location);

      // Return the location data
      return location;
    } catch (error) {
      // Log any errors encountered during the request
      console.error("Error validating location:", error);
    }
  };

  // Handle the sending of messages in the chat
  const handleSendMessage = async () => {
    if (selectedChat) {
      if (UserChatData.showStopSlider) {
        // Handle input of the number of user stops
        addMessage(selectedChat.id, setChats, UserChatData.stops);
        UserChatData.showStopSlider = false; // Hide the stop slider
      } else if (chatInput.showAddressInput) {
        // Handle address input message
        const address =
          UserChatData.locationType === "start"
            ? UserChatData.startAddress
            : UserChatData.endAddress;

        addMessage(
          selectedChat.id,
          setChats,
          `${address[0]} ${address[1]} ${address[2]} ${address[3]}`
        );

        // Reset input field and hide address input
        setChatInput({
          ...chatInput,
          message: "",
          showAddressInput: false,
        });
        
        UserChatData.startConfirmed = await validateLocation(`${address[0]} ${address[1]} ${address[2]} ${address[3]}`, false);

      } else if (chatInput.message.trim() !== "") {
        // Handle regular message submission
        addMessage(selectedChat.id, setChats, chatInput.message);

        // Store the message if action is "City Name"
        if (UserChatData.action === "City Name") {
          if (UserChatData.locationType === "start") {
            UserChatData.startAddress[1] = chatInput.message;
          } else if (UserChatData.locationType === "end") {
            UserChatData.endAddress[1] = chatInput.message;
          }
        }

        // Reset the input field
        setChatInput({
          ...chatInput,
          message: "",
        });
      }

      // Notify the workflow that the data has been submitted
      UserChatData.submitted = true;
    }
  };

  // Handle the creation of a new chat
  const handleNewChat = () => {
    // Generate a new chat ID and add a new chat to the list
    const maxId = chats.reduce((max, chat) => Math.max(max, chat.id), 0);
    const newChatId = maxId + 1;
    const newChat = {
      id: newChatId,
      title: `Chat ${newChatId}`,
      messages: initialMessage,
    };
    setChats((prevChats) => [...prevChats, newChat]);
    setSelectedChat(newChat); // Select the newly created chat
  };

  // Handle the deletion of a chat
  const handleDeleteChat = (chatId) => {
    setChats((prevChats) => prevChats.filter((chat) => chat.id !== chatId));
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
              onClick={() => handleAddChat(chat)}
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
            <MapButton />
          </Box>
          <Box sx={{ mb: -1, width: "100%" }}>
            <ItineraryButton />
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
              {selectedChat.messages.map((message, index) =>
                typeof message === "string" ? (
                  <Box
                    key={index}
                    className={`message ${index % 2 === 0 ? "bot" : "user"}`}
                  >
                    <Typography variant="body1">{message}</Typography>
                  </Box>
                ) : (
                  <Box key={index} className="message-container user">
                    <Box className="message user">
                      <Typography variant="body1">{message.text}</Typography>
                    </Box>
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
                )
              )}
              <div ref={chatEndRef} /> {/* Scroll to bottom */}
            </Box>
          ) : (
            <Typography variant="body1">Select a chat to start</Typography>
          )}
        </Box>

        {/* Input area for typing and sending messages */}
        <Box className="input-area">
          {chatInput.showAddressInput ? (
            <AddressBar /> // Show AddressBar if address input is required
          ) : UserChatData.showStopSlider ? (
            <StopSlider /> // Show StopSlider if stop input is required
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
          >
            Send
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default ChatPage;
