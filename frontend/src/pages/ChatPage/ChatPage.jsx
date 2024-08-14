import React, { useState, useRef, useEffect } from "react";
import { Box, TextField, Button, Typography } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import MapButton from "../../components/buttons/MapButton";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import "./ChatPage.css";

const ChatPage = () => {
  // State to store the list of chats
  const [chats, setChats] = useState([
    {
      id: 1,
      title: "Chat 1",
      messages: [
        "Hello this is journey genie! I would love to help you with your trip. Where will you be starting?",
      ],
    },
    {
      id: 2,
      title: "Chat 2",
      messages: [
        "Hi! I need some information.",
        "Of course! What do you need help with?",
      ],
    },
  ]);

  // State to store the currently selected chat
  const [selectedChat, setSelectedChat] = useState(null);

  // State to store the current message being typed by the user
  const [currentMessage, setCurrentMessage] = useState("");

  // State to manage the visibility of the prompt box
  const [showPrompt, setShowPrompt] = useState(true);

  // State to track if the send button is disabled
  const [sendButtonDisabled, setSendButtonDisabled] = useState(true);
  
  // Ref to keep track of the end of the chat for scrolling
  const chatEndRef = useRef(null);

  // Effect to set the first chat as the selected chat when the component loads
  useEffect(() => {
    if (chats.length > 0) {
      setSelectedChat(chats[0]);
    }
  }, [chats]);

  // Function to handle selecting a chat from the sidebar
  const handleChatClick = (chat) => {
    setSelectedChat(chat);
  };

  // Effect to scroll to the end of the chat when a new message is added
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);

  // Function to handle typing in the message input field
  const handleInputChange = (event) => {
    setCurrentMessage(event.target.value);
  };

  // Function to handle sending a message
  const handleSendMessage = () => {
    if (currentMessage.trim() !== "" && selectedChat) {
      // Add the new message to the selected chat's messages array
      setSelectedChat((prevChat) => ({
        ...prevChat,
        messages: [...prevChat.messages, currentMessage],
      }));
      setCurrentMessage("");
    }
  };

  const handleNewChat = () => {
    // Finds the chat that contains the highest ID and stores the ID value
    const maxId = chats.reduce((max, chat) => Math.max(max, chat.id), 0);
    // Increment ID by 1
    const newChatId = maxId + 1;
    // Generate a new chat to be stored in chats
    const newChat = {
      id: newChatId,
      title: `Chat ${newChatId}`,
      messages: [],
    };
    // Adds this chat to chats along with all the previous chats
    setChats((prevChats) => [...prevChats, newChat]);
    setSelectedChat(newChat);
  };

  // Function to handle deleting a chat
  const handleDeleteChat = (chatId) => {
    // Filter out the chat with the given ID
    setChats((prevChats) => prevChats.filter((chat) => chat.id !== chatId));
    // If the deleted chat was selected, clear the selection
    if (selectedChat?.id === chatId) {
      setSelectedChat(null);
    }
  };

  // Function to handle pressing Enter to send a message
  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault(); // Prevent the default Enter key behavior
      handleSendMessage();
    }
  };

  // Function to handle the user's choice from the prompt box
  const handleOptionClick = (option) => {
    console.log(`User selected: ${option}`);
    setSendButtonDisabled(false); // Re-enable send button after option is chosen
    setShowPrompt(false); // Hide the prompt box
  };

  return (
    <Box className="page-container">
      {/* Sidebar with chat logs and navigation buttons */}
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
        <Box className="chat-logs">
          {chats.map((chat) => (
            <Box
              key={chat.id}
              className={`chat-item ${
                selectedChat?.id === chat.id ? "selected" : ""
              }`}
              onClick={() => handleChatClick(chat)}
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
                    e.stopPropagation(); // Prevent triggering onClick on Box
                    handleDeleteChat(chat.id);
                  }}
                />
              </Box>
            </Box>
          ))}
        </Box>

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

      {/* Main content area for displaying selected chat and sending messages */}
      <Box className="main-content">
        <Box className="header">
          <Typography variant="h6" color="white">
            Journey Genie
          </Typography>
        </Box>

        <Box className="chat-box">
          {selectedChat ? (
            <Box className="chat-messages">
              {selectedChat.messages.map((message, index) => (
                <Box
                  key={index}
                  className="message"
                  sx={{
                    alignSelf: index % 2 === 0 ? "flex-start" : "flex-end",
                  }}
                >
                  <Typography variant="body1">{message}</Typography>
                </Box>
              ))}
              <div ref={chatEndRef} />
            </Box>
          ) : (
            <Typography variant="body1" color="white">
              Select a chat to view messages
            </Typography>
          )}
        </Box>

        {/* Prompt Box */}
        {showPrompt && (
          <Box className="prompt-box">
            <Typography variant="body1">Please choose an option:</Typography>
            <Button
              variant="contained"
              onClick={() => handleOptionClick("city_name")}
            >
              City Name
            </Button>
            <Button
              variant="contained"
              onClick={() => handleOptionClick("address")}
            >
              Address
            </Button>
            <Button
              variant="contained"
              onClick={() => handleOptionClick("current_location")}
            >
              Use Current Location
            </Button>
          </Box>
        )}

        <Box className="input-area">
          <TextField
            variant="outlined"
            placeholder="Type a message"
            value={currentMessage}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            sx={{ flex: 1, bgcolor: "white", borderRadius: 1, mr: 2 }}
            disabled={sendButtonDisabled} // Disable input if send button is disabled
          />
          <Button
            variant="contained"
            color="green"
            sx={{ color: "white.light" }}
            onClick={handleSendMessage}
            disabled={sendButtonDisabled} // Disable send button until an option is chosen
          >
            Send
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default ChatPage;