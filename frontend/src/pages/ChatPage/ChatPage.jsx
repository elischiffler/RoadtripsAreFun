import React, { useState, useRef, useEffect } from "react";
import { Box, TextField, Button, Typography } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import MapButton from "../../components/buttons/MapButton";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import Slider from '@mui/material/Slider';
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
      userInputType: null,
      start: null,
      end: null,
      numStops: 0,
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
      end: null,
      numStops: 0,
    },
  ]);

  const [selectedChat, setSelectedChat] = useState(null);
  const [currentMessage, setCurrentMessage] = useState("");
  const [currentAddress, setCurrentAddress] = useState("");
  const [currentZip, setCurrentZip] = useState("");
  const [currentCity, setCurrentCity] = useState("");
  const [currentState, setCurrentState] = useState("");
  const chatEndRef = useRef(null);

  // State to hold the slider value
  const [sliderValue, setSliderValue] = useState(5);

  // Function to handle slider value change
  const handleSliderChange = (event, newValue) => {
    setSliderValue(newValue);
  };

  function valuetext(value) {
    return `${value} stops`;
  }

  useEffect(() => {
    if (chats.length > 0 && !selectedChat) {
      setSelectedChat(chats[0]);
    }
  }, [chats, selectedChat]);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);

  const handleChatClick = (chat) => {
    setSelectedChat(chat);
  };

  const handleInputChange = (event) => {
    setCurrentMessage(event.target.value);
  };

  const handleSendMessage = () => {
    if (selectedChat && selectedChat.numStops === 0) {
      let updatedStart = selectedChat.start ? selectedChat.start : null;
      if (selectedChat.userInputType === "city_name") {
        updatedStart = currentCity;
      } else if (selectedChat.userInputType === "address") {
        updatedStart = `${currentAddress}, ${currentZip}, ${currentCity}, ${currentState}`;
      }

      const updatedChat = selectedChat.end? {
        ...selectedChat,
        numStops: sliderValue,
        messages: [...selectedChat.messages, `Number of stops ${sliderValue}`],
      }: 
      selectedChat.start? {
        ...selectedChat,
        end: updatedStart,
        userInputType: null,
        messages: [...selectedChat.messages, updatedStart],
      }: {
        ...selectedChat,
        start: updatedStart,
        showPrompt: true,
        messages: [...selectedChat.messages, updatedStart],
      };

      const updatedChats = chats.map((chat) =>
        chat.id === updatedChat.id ? updatedChat : chat
      );

      setChats(updatedChats);
      setSelectedChat(updatedChat);
      setCurrentMessage("");
      setCurrentAddress("");
      setCurrentZip("");
      setCurrentCity("");
      setCurrentState("");
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
      start: null,
      end: null,
      numStops: 0,
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

  const getCurrentLocation = (callback) => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          callback(position.coords.latitude, position.coords.longitude);
        },
        (error) => {
          console.error("Error getting location:", error);
        }
      );
    } else {
      console.error("Geolocation is not supported by this browser.");
    }
  };

  const handleOptionClick = (option) => {
    if (selectedChat) {
      console.log(`User selected: ${option}`);

      let inputType = null;
      if (option === "city_name") {
        inputType = "city_name";
      } else if (option === "address") {
        inputType = "address";
      } else if (option === "current_location") {
        inputType = "current_location";
        getCurrentLocation((lat, lng) => {
          const endPoint= `Latitude: ${lat}, Longitude: ${lng}`;
          const updatedChat = selectedChat.start ? {
            ...selectedChat,
            showPrompt: false,
            end: endPoint, // Set the location as the end value
            messages: [...selectedChat.messages, endPoint],
          } : {
            ...selectedChat,
            showPrompt: true,
            start: endPoint, // Set the location as the start value
            messages: [...selectedChat.messages, endPoint],
          };

          const updatedChats = chats.map((chat) =>
            chat.id === updatedChat.id ? updatedChat : chat
          );

          setChats(updatedChats);
          setSelectedChat(updatedChat);
        });
        return;
      }

      const updatedChat = {
        ...selectedChat,
        showPrompt: false,
        userInputType: inputType,
      };

      const updatedChats = chats.map((chat) =>
        chat.id === updatedChat.id ? updatedChat : chat
      );

      setChats(updatedChats);
      setSelectedChat(updatedChat);
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

        {selectedChat && selectedChat.showPrompt && (
          <Box className="prompt-box">{selectedChat.start?
            <Typography variant="body1">Please choose how you want to select your ending location:</Typography>:
            <Typography variant="body1">Please choose how you want to select your starting location:</Typography> }
            
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

            {/* Logic for after both start and end points are set */}
            {selectedChat.end && selectedChat.numStops === 0 && (
              <Slider
              aria-label="Temperature"
              defaultValue={5}
              getAriaValueText={valuetext}
              valueLabelDisplay="auto"
              shiftStep={10}
              color="green"
              value = {sliderValue}
              onChange={handleSliderChange}
              step={1}
              marks
              min={1}
              max={10}
            />

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