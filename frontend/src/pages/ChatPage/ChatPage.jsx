import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  TextField,
  Button,
  Typography,
} from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/ItineraryButton";
import MapButton from "../../components/MapButton";
import "./ChatPage.css";

const ChatPage = () => {
  const [selectedChat, setSelectedChat] = useState(null);
  const chatEndRef = useRef(null);

  const chats = [
    {
      id: 1,
      title: "Chat 1",
      messages: [
        "Hello! How can I help you?",
        "I'm looking for information on local attractions.",
        "Sure, I can help with that. What kind of attractions are you interested in?",
        "I love historical sites and museums.",
        "Great! There are several historical sites and museums in the area. Let me provide you with some recommendations.",
        "The local history museum is very informative.",
        "You might also enjoy the old town district, which has several well-preserved buildings.",
        "Thanks for the tips! Can you suggest any good restaurants nearby?",
        "Absolutely! There are a few restaurants in the area that serve excellent local cuisine.",
        "I appreciate your help!",
      ],
    },
    {
      id: 2,
      title: "Chat 2",
      messages: [
        "Hi! I need some information.",
        "Of course! What do you need help with?",
        "I'm planning a road trip and need some tips on the best routes.",
        "I can definitely assist with that. Are you looking for scenic routes or the fastest routes?",
        "Scenic routes would be great. I want to enjoy the journey.",
        "Got it! I'll provide you with some scenic routes that will make your trip enjoyable.",
        "Have you considered the coastal drive? It offers stunning views of the ocean.",
        "That sounds amazing! Are there any specific stops I should make?",
        "Definitely. There are several beautiful beaches and lookout points along the way.",
        "Awesome, I'll add those to my itinerary. Thanks for the help!",
      ],
    },
  ];

  useEffect(() => {
    if (chats.length > 0) {
      setSelectedChat(chats[0]);
    }
  }, []);

  const handleChatClick = (chat) => {
    setSelectedChat(chat);
  };

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);

  return (
    <Box className="page-container">
      <Box className="sidebar">
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
                color:
                  selectedChat?.id === chat.id ? "white" : "text.primary",
              }}
            >
              <Typography variant="body2">{chat.title}</Typography>
            </Box>
          ))}
        </Box>

        <Box className="sidebar-bottom">
          <Box sx={{ mb: 2, width: "100%" }}>
            <MapButton />
          </Box>
          <Box sx={{ mb: 2, width: "100%" }}>
            <ItineraryButton />
          </Box>
          <LogoButton />
        </Box>
      </Box>

      <Box className="main-content">
        <Box className="header">
          <Typography variant="h6" color="white">
            JourneyGenie
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

        <Box className="input-area">
          <TextField
            variant="outlined"
            placeholder="Type a message"
            sx={{ flex: 1, bgcolor: "white", borderRadius: 1, mr: 2 }}
          />
          <Button
            variant="contained"
            color="green"
            sx={{ color: "white.light" }}
          >
            Send
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default ChatPage;
