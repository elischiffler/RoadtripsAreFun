import React, { useState, useRef, useEffect, useContext } from "react";
import { Box, TextField, Button, Typography } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import MapButton from "../../components/buttons/MapButton";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import { startWorkFlow, addMessage } from "./startWorkFlow";
import StopSlider from "./InputStops";
import AddressBar from "./InputAddress";
import { UserChatDataContext } from "../../states/UserChatDataContext";
import "./ChatPage.css";

const ChatPage = () => {
  // Grabs the global instance of UserChatData
  const UserChatData = useContext(UserChatDataContext);

  const initialMessage = [
    "Hello there! I’m Journey Genie, and I’m excited to help you with your trip planning. To get started, could you please tell me what type of location you'd like to use?",
  ];

  const [chats, setChats] = useState([
    {
      id: 1,
      title: "Chat 1",
      messages: initialMessage,
    },
  ]);

  const [selectedChat, setSelectedChat] = useState(null);
  const [chatInput, setChatInput] = useState({
    name: "Type a Message",
    message: "",
    showAddressInput: false,
  });
  const chatEndRef = useRef(null);

  // Starts the workflow on page first load and when a new chat is selected
  useEffect(() => {
    if (selectedChat && !UserChatData.workflowStarted) {
      startWorkFlow(
        setChats,
        selectedChat.id,
        setChatInput,
        chatInput,
        UserChatData
      );
      UserChatData.workflowStarted = true; // Ensure this flag is properly managed
    }
  }, [selectedChat]);

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
    if (selectedChat) {
      if (UserChatData.showStopSlider) {
        // Input the number of user stops
        addMessage(selectedChat.id, setChats, UserChatData.stops);
        console.log(UserChatData.stops);
        // Remove the slider
        UserChatData.showStopSlider = false;
      } else if (chatInput.showAddressInput) {
        // Adds a structured version of the users message in address box
        // Determine what data is displayed
        if (UserChatData.locationType === "start") {
          addMessage(
            selectedChat.id,
            setChats,
            `${UserChatData.startAddress[0]} ${UserChatData.startAddress[1]} ${UserChatData.startAddress[2]} ${UserChatData.startAddress[3]}`
          );
        } else if (UserChatData.locationType === "end") {
          addMessage(
            selectedChat.id,
            setChats,
            `${UserChatData.endAddress[0]} ${UserChatData.endAddress[1]} ${UserChatData.endAddress[2]} ${UserChatData.endAddress[3]}`
          );
        }

        // Reset the input field and hide address input
        setChatInput({
          ...chatInput,
          message: "",
          showAddressInput: false,
        });
      } else if (chatInput.message.trim() !== "") {
        // Handle regular message submission
        addMessage(selectedChat.id, chatInput.message, setChats);

        // Reset the input field
        setChatInput({
          ...chatInput,
          message: "",
        });
      }

      // Notifys the workflow that they submitted there data
      UserChatData.submitted = true;
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
                          onClick={() => (UserChatData.action = button.action)}
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
          ) : UserChatData.showStopSlider ? (
            <StopSlider />
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
