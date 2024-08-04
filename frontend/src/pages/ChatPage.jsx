import React, { useState, useRef } from "react";
import {
  Box,
  CssBaseline,
  TextField,
  Button,
  Typography,
  ThemeProvider,
} from "@mui/material";
import customTheme from "../components/Theme";
import LogoButton from "../components/LogoButton";
import ItineraryButton from "../components/ItineraryButton";
import MapButton from "../components/MapButton";

const ChatPage = () => {
  const [selectedChat, setSelectedChat] = useState(null);
  const chatEndRef = useRef(null); // Ref to scroll to the end of the chat

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

  const handleChatClick = (chat) => {
    setSelectedChat(chat);
  };

  // Scroll to bottom when new messages are added
  React.useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);

  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Box
        sx={{
          display: "flex",
          height: "100vh",
          overflow: "hidden",
          boxSizing: "border-box",
        }}
      >
        {/* Left Sidebar */}
        <Box
          sx={{
            width: "17%",
            bgcolor: "pink.main",
            display: "flex",
            flexDirection: "column",
            padding: 2,
            boxShadow: 1,
            borderRight: `2px solid ${customTheme.palette.purple.main}`,
            boxSizing: "border-box",
          }}
        >
          {/* Chat Logs */}
          <Box
            sx={{
              flex: 1,
              overflowY: "auto",
              mb: 2,
              display: "flex",
              flexDirection: "column",
            }}
          >
            {chats.map((chat) => (
              <Box
                key={chat.id}
                sx={{
                  padding: 1,
                  borderRadius: 1,
                  cursor: "pointer",
                  mb: 1,
                  border: `2px solid ${customTheme.palette.purple.main}`,
                  bgcolor:
                    selectedChat?.id === chat.id
                      ? "purple.main"
                      : "rgba(229, 208, 227, 0.5)",
                  "&:hover": {
                    backgroundColor: "purple.main",
                    color: "white",
                  },
                  color:
                    selectedChat?.id === chat.id ? "white" : "text.primary",
                }}
                onClick={() => handleChatClick(chat)}
              >
                <Typography variant="body2">{chat.title}</Typography>
              </Box>
            ))}
          </Box>

          {/* Sidebar Bottom */}
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              boxSizing: "border-box",
              width: "100%",
              padding: 1,
              bgcolor: "pink.main",
              borderTop: `2px solid ${customTheme.palette.purple.main}`,
              position: "sticky",
              bottom: 0,
            }}
          >
            <Box sx={{ mb: 2, width: "100%" }}>
              <MapButton />
            </Box>
            <Box sx={{ mb: 2, width: "100%" }}>
              <ItineraryButton />
            </Box>
            <LogoButton />
          </Box>
        </Box>

        {/* Main Content */}
        <Box
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            boxSizing: "border-box",
          }}
        >
          {/* Header */}
          <Box
            sx={{
              width: "100%",
              bgcolor: "primary.main",
              padding: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: 1,
            }}
          >
            <Typography variant="h6" color="white">
              JourneyGenie
            </Typography>
          </Box>

          {/* Chat Container */}
          <Box
            sx={{
              flex: 1,
              overflowY: "auto",
              padding: 2,
              bgcolor: "primary.main",
              display: "flex",
              flexDirection: "column",
              gap: 2, // Add space between messages
              boxSizing: "border-box",
            }}
          >
            {selectedChat ? (
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 2,
                  maxHeight: "calc(100vh - 150px)", // Adjust to fit screen
                  overflowY: "auto",
                  boxSizing: "border-box",
                }}
              >
                {selectedChat.messages.map((message, index) => (
                  <Box
                    key={index}
                    sx={{
                      alignSelf: index % 2 === 0 ? "flex-start" : "flex-end",
                      bgcolor: "pink.main",
                      padding: 2,
                      borderRadius: 2,
                      maxWidth: "75%",
                      boxSizing: "border-box",
                    }}
                  >
                    <Typography variant="body1">{message}</Typography>
                  </Box>
                ))}
                <div ref={chatEndRef} />{" "}
                {/* Empty div to help scroll to bottom */}
              </Box>
            ) : (
              <Typography variant="body1" color="white">
                Select a chat to view messages
              </Typography>
            )}
          </Box>

          {/* Input Area */}
          <Box
            sx={{
              width: "83%",
              display: "flex",
              padding: 2,
              boxShadow: 1,
              position: "fixed",
              bottom: 0,
              bgcolor: "primary.main",
              boxSizing: "border-box",
            }}
          >
            <TextField
              variant="outlined"
              placeholder="Type a message"
              sx={{ flex: 1, bgcolor: "white", borderRadius: 1, mr: 2 }}
            />
            <Button variant="contained" color="secondary">
              Send
            </Button>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default ChatPage;
