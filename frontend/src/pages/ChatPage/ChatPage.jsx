import React, { useState, useRef, useEffect } from "react";
import { Box, TextField, Button, Typography } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import MapButton from "../../components/buttons/MapButton";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { locationButtonClick } from "./LocationType";
import AddressBar from "./InputAddress";
import "./ChatPage.css";

const ChatPage = () => {
  const initialMessageCluster = [
    "Hello there! I’m Journey Genie, and I’m excited to help you with your trip planning. To get started, could you please tell me what type of location you'd like to use?",
    {
      text: "I would like to use my:",
      buttons: [
        { label: "Address", action: "Address" },
        { label: "City Name", action: "City Name" },
        { label: "Current Location", action: "Current Location" },
      ],
    },
  ];

  const [chats, setChats] = useState([
    {
      id: 1,
      title: "Chat 1",
      messages: initialMessageCluster,
    },
  ]);

  const [selectedChat, setSelectedChat] = useState(null);
  const [chatInput, setChatInput] = useState({
    name: "Type a Message",
    message: "",
    showAddressInput: false,
  });
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
    if (chatInput.message.trim() !== "" && selectedChat) {
      // Add the inputted message into the chat log
      setSelectedChat((prevChat) => ({
        ...prevChat,
        messages: [...prevChat.messages, chatInput.message],
      }));

      // Clear input box message
      setChatInput({
        ...chatInput,
        message: "",
      });

      // Change input bar back to default if changed prior
      setChatInput({
        ...chatInput,
        showAddressInput: false,
      });
    }
  };

  const handleNewChat = () => {
    const maxId = chats.reduce((max, chat) => Math.max(max, chat.id), 0);
    const newChatId = maxId + 1;
    const newChat = {
      id: newChatId,
      title: `Chat ${newChatId}`,
      messages: initialMessageCluster,
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
      handleSendMessage();
    }
  };

  return (
    <Box className="page-container">
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
                    e.stopPropagation();
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

      <Box className="main-content">
        <Box className="header">
          <Typography variant="h6" color="white">
            Journey Genie
          </Typography>
        </Box>

        <Box className="chat-box">
          {selectedChat ? (
            <Box className="chat-messages">
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
                          onClick={() =>
                            locationButtonClick(
                              setChats,
                              selectedChat.id,
                              button.action,
                              setChatInput,
                              chatInput
                            )
                          }
                        >
                          {button.label}
                        </Button>
                      ))}
                    </Box>
                  </Box>
                )
              )}
              <div ref={chatEndRef} />
            </Box>
          ) : (
            <Typography variant="body1">Select a chat to start</Typography>
          )}
        </Box>

        <Box className="input-area">
          {chatInput.showAddressInput ? (
            <AddressBar /> // Show AddressBar if condition is true
          ) : (
            <TextField
              label={chatInput.name}
              placeholder={chatInput.name}
              value={chatInput.message}
              onChange={(e) =>
                setChatInput({
                  ...chatInput,
                  message: e.target.value,
                })
              }
              onKeyDown={handleKeyDown}
              variant="outlined"
              fullWidth
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
