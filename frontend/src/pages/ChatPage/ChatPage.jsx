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
    
  ]);

  // All use states are initialized to manage chat page display
  const [selectedChat, setSelectedChat] = useState(null);
  const [currentMessage, setCurrentMessage] = useState("");
  const [currentAddress, setCurrentAddress] = useState("");
  const [currentZip, setCurrentZip] = useState("");
  const [currentCity, setCurrentCity] = useState("");
  const [currentState, setCurrentState] = useState("");
  const chatEndRef = useRef(null);
  const [sliderValue, setSliderValue] = useState(5);

  // Function to handle slider value change
  const handleSliderChange = (event, newValue) => {
    setSliderValue(newValue);
  };

  // Creates a user understandable label
  function valuetext(value) {
    return `${value} stops`;
  }


  // Sets a default chat if available on startup
  useEffect(() => {
    if (chats.length > 0 && !selectedChat) {
      setSelectedChat(chats[0]);
    }
  }, [chats, selectedChat]);


  // Scrollbar behavior handling
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [selectedChat]);


  // Handles switching chats based on clicks
  const handleChatClick = (chat) => {
    setSelectedChat(chat);
  };

  // TODO add back the default chat box once everything works this will be used to send chats
  const handleInputChange = (event) => {
    setCurrentMessage(event.target.value);
  };

  // Sends an API request to our backend catching errors as needed
  const validateLocation = async (start, isCoordinate = false) => {
    try {
      const queryParam = isCoordinate ? `coordinates=${encodeURIComponent(start)}` : `address=${encodeURIComponent(start)}`;
      const response = await fetch(`/validate-location?${queryParam}`);
  
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
  
      const location = await response.text();
      console.log('Validated Location:', location);
      
      // Handle the response data as needed
      return location;
      
    } catch (error) {
      console.error('Error validating location:', error);
    }
  };

  // Currently works as the method for determining everything when the send button is clicked
  const handleSendMessage = () => {
    // Checking to see if the basic requirements have been sent
    if (selectedChat && selectedChat.numStops === 0) {
      // initializes updatedStart value to be altered
      let updatedStart = selectedChat.start ? selectedChat.start : null;
      // Formats the updatedStart value based on inputType
      if (selectedChat.userInputType === "city_name") {
        updatedStart = currentCity;
      } else if (selectedChat.userInputType === "address") {
        updatedStart = `${currentAddress}, ${currentZip}, ${currentCity}, ${currentState}`;
      }

      // Creates an updatedChat based on what requirement still needs to be fullfilled
      const updatedChat = selectedChat.end? {
        ...selectedChat,
        numStops: sliderValue,
        messages: [...selectedChat.messages, `Number of stops: ${sliderValue}`],
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

      // Maps the chats to include the updated chat
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

      // Requires backend to be deployed but will get the string response from our backend API
      if (selectedChat.end && selectedChat.numStops === 0){
        location = validateLocation(end);
      }
      else if (selectedChat.numStops === 0){
        location = validateLocation(start);
      }

    }
  };

  {/* Logic for creating new chats */}
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


  {/* For deleting chats */}
  const handleDeleteChat = (chatId) => {
    setChats((prevChats) => prevChats.filter((chat) => chat.id !== chatId));
    if (selectedChat?.id === chatId) {
      setSelectedChat(null);
    }
  };


  {/* Functionality for using enter key within boxes*/}
  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSendMessage();
    }
  };

  {/* Function that gets the users current location */}
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

  {/* Handles the option for start or end location input preference */}
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

        {/* The chatboxes format */}
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

        {/* Prompt box */}
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

            {/* Logic for after both start and end points are set and adds a scrollbar to adjust */}
            {selectedChat.end && selectedChat.numStops === 0 && (
              <>
                <Typography variant="body1"
                align="left"
                >Please enter the number of stops:</Typography>
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
            </>
            )}

            {/* The send button */}
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