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
  const initialMessage =
    "Hello, this is Journey Genie! I would love to help you with your trip. Where will you be starting?";

  const [chats, setChats] = useState([
    {
      id: 1,
      title: "Chat 1",
      messages: [initialMessage],
      showPrompt: true,
      userInputType: null, // New state to determine what input to show
      start: null, // state to hold the starting value
      end: null, // state to hold the ending point value

    },
    {
      id: 2,
      title: "Chat 2",
      messages: [
        "Hi! I need some information.",
        "Of course! What do you need help with?",
      ],
      showPrompt: false,
      userInputType: null,
      start: null,
      end: null
    },
  ]);

  const [selectedChat, setSelectedChat] = useState(null);
  const [currentMessage, setCurrentMessage] = useState("");
  const [currentAddress, setCurrentAddress] = useState("");
  const [currentZip, setCurrentZip] = useState("");
  const [currentCity, setCurrentCity] = useState("");
  const [currentState, setCurrentState] = useState("")
  const chatEndRef = useRef(null);

  useEffect(() => {
    if (chats.length > 0) {
      setSelectedChat(chats[0]);
    }
  }, [chats]);

  const handleChatClick = (chat) => {
    setSelectedChat(chat);
  };

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);


  const handleSendMessage = () => {
    if (currentMessage.trim() !== "" && selectedChat) {
      setSelectedChat((prevChat) => {
        const updatedChat = {
          ...prevChat,
          messages: [...prevChat.messages, currentMessage],
        };

        const updatedChats = chats.map((chat) =>
          chat.id === updatedChat.id ? updatedChat : chat
        );

        setChats(updatedChats);

        return updatedChat;
      });

      setCurrentMessage("");
    }
  };

  const handleNewChat = () => {
    const maxId = chats.reduce((max, chat) => Math.max(max, chat.id), 0);
    const newChatId = maxId + 1;
    const newChat = {
      id: newChatId,
      title: `Chat ${newChatId}`,
      messages: [initialMessage],
      showPrompt: true,
      userInputType: null,
    };
    setChats((prevChats) => [...prevChats, newChat]);
    setSelectedChat(newChat);
  };

  const handleDeleteChat = (chatId) => {
    setChats((prevChats) => prevChats.filter((chat) => chat.id !== chatId));
    if (selectedChat?.id === chatId) {
      setSelectedChat(null);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();

      if (selectedChat) {
        // Update the start or end based on user input type
        setSelectedChat((prevChat) => {
          let updatedChat = { ...prevChat };

          if (prevChat.userInputType === "city_name") {
            updatedChat.start = currentCity;
          } else if (prevChat.userInputType === "address") {
            updatedChat.start = currentAddress.concat(", ", currentZip,
               ", ", currentCity,
                ", ", currentState);
          }

          const updatedChats = chats.map((chat) =>
            chat.id === updatedChat.id ? updatedChat : chat
          );

          setChats(updatedChats);

          return updatedChat;
        });

        // Reset the input fields after submission
        setCurrentAddress("");
        setCurrentZip("");
        setCurrentCity("");
        setCurrentState("");
        
      }
      setCurrentMessage(selectedChat.start);
      handleSendMessage();
    }
  };

  const handleOptionClick = (option) => {
    if (selectedChat) {
      console.log(`User selected: ${option}`);

      // Determine the input type based on the user's selection
      let inputType = null;
      if (option === "city_name") {
        inputType = "city_name";
      } else if (option === "address") {
        inputType = "address";
      } else if (option === "current_location") {
        inputType = "current_location";
      }

      // Update the state with the new input type and hide the prompt
      const updatedChat = {
        ...selectedChat,
        showPrompt: false,
        userInputType: inputType,
      };

      const updatedChats = chats.map((chat) =>
        chat.id === updatedChat.id ? updatedChat : chat
      );

      setChats(updatedChats);
      setSelectedChat(updatedChat); // Update the selectedChat state
    }
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
        {selectedChat && selectedChat.showPrompt && (
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

        {/* Input Field */}
        {selectedChat && !selectedChat.showPrompt && (
          <Box className="input-area">
            {selectedChat.userInputType === "city_name" && (
              <TextField
                value={currentCity}
                onChange={(e) => setCurrentCity(e.target.value)}
                onKeyDown={handleKeyDown}
                variant="outlined"
                placeholder="Enter city name..."
                fullWidth
              />
            )}

            {selectedChat.userInputType === "address" && (
              <>
                <TextField
                  value={currentAddress}
                  onChange={(e) => setCurrentAddress(e.target.value)}
                  onKeyDown={handleKeyDown}
                  variant="outlined"
                  placeholder="Enter address..."
                  fullWidth
                />
                <TextField
                  value={currentZip}
                  onChange={(e) => setCurrentZip(e.target.value)}
                  onKeyDown={handleKeyDown}
                  variant="outlined"
                  placeholder="Enter zip code..."
                  fullWidth
                />
                <TextField
                  value={currentCity}
                  onChange={(e) => setCurrentCity(e.target.value)}
                  onKeyDown={handleKeyDown}
                  variant="outlined"
                  placeholder="Enter city..."
                  fullWidth
                />
                <TextField
                  value={currentState}
                  onChange={(e) => setCurrentState(e.target.value)}
                  onKeyDown={handleKeyDown}
                  variant="outlined"
                  placeholder="Enter state..."
                  fullWidth
                />
              </>
            )}

            <Button
              variant="contained"
              color="green"
              sx={{ color: "white.light" }}
              onClick={handleSendMessage}
              disabled={selectedChat?.showPrompt} // Disable send button until an option is chosen
            >
            Send
            </Button>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default ChatPage;