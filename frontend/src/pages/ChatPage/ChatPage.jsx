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
import { UserDataContext } from "../../states/UserDataContext";
import { validateLocation } from "./ValidateLocation";
import "./ChatPage.css";

const ChatPage = () => {

  // Retrieve the global instance of UserData
  const UserData = useContext(UserDataContext);
  // Grab the chat logs
  const ChatLogsData = UserData.chatlogs;
  // State to track current chats data
  const [UserChatData, setUserChatData] = useState(ChatLogsData?.chatdata?.length > 0?
    ChatLogsData.chatdata[ChatLogsData.currentId-1]:
    ChatLogsData.createChatData(1));

  // Initial message displayed in a new chat
  const initialMessage = [
    "Hello there! I’m Journey Genie, and I’m excited to help you with your trip planning. To get started, could you please tell me what type of location you'd like to use?",
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
  const [workflowStarted, setWorkflowStarted] = useState(UserChatData.workflowStarted);
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
      );
      // Mark the workflow as started
      setWorkflowStarted(true);
    }
  }, [selectedChat, workflowStarted, UserChatData]);

  // Saves the UserData whenever the there are changes to chat data or the chats
  useEffect(() => {
    saveUserData();
    console.log("Current chat data: ", UserChatData);
  }, [UserChatData, selectedChat, chats, UserChatData.locationType])

  // Automatically load chats from local storage or create a chat during the initial mount
  useEffect(() => {
    const savedChats = sessionStorage.getItem("chats");
    if (savedChats && savedChats.length > 2) { // Check that more than an empty array is returned
      const parsedChats = JSON.parse(savedChats);
      setChats(parsedChats);
      console.log("Loaded chats from sessionStorage:", parsedChats);
    } else {
      const initialChats = [
        {
          id: 1,
          title: "Chat 1",
          messages: initialMessage,
        },
      ];
      setChats(initialChats);
      console.log("Initialized chats with default:", initialChats);
    }
  }, []);

  // Effect to handle users navigating away from the page
  useEffect(() => {
    const handleBeforeUnload = (event) => {
      console.log("User is about to leave the page.");

      saveUserData();

      // If you want to prompt the user before leaving
      event.preventDefault();
      event.returnValue = ''; // Chrome requires returnValue to be set
      
    };

    // Event listener to detect if the user is navigating away/refreshing
    window.addEventListener('beforeunload', handleBeforeUnload);

    // Cleanup the event listener when the component unmounts
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);

  // Automatically setSelected chat on initial mount
  useEffect(() => {
    if (chats.length > 0) {
      const chatId = UserChatData.chatId - 1;
      if (chatId >= 0 && chatId < chats.length) {
        setSelectedChat(chats[chatId]);
      } else {
        console.error("Invalid chat ID:", UserChatData.chatId);
      }
    }
  }, [chats, UserChatData.chatId]);


  const saveUserData = () => {
    if(chats.length>0 && UserChatData.update){
      // Save chats to the session storage
      sessionStorage.setItem("chats", JSON.stringify(chats));
      console.log("Saved chats to sessionStorage:", chats);

      console.log("Saved data to sessionStorage: ", UserData);
      // Save the UserData to the session
      sessionStorage.setItem(
        "UserData",
        JSON.stringify({
          chatlogs: {
            chatdata: UserData.chatlogs.chatdata,
            currentId: UserData.chatlogs.currentId,
          },
        })
      );
    };
  };

  // Handle chat selection from the sidebar
  const handleSelectChat = (chat) => {
    const selectedChatData = ChatLogsData.getChatDataById(chat.id);
    setSelectedChat({ ...chat, ...selectedChatData });
    setUserChatData(ChatLogsData.getChatDataById(chat.id));
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
        addMessage(selectedChat.id, setChats, UserChatData.stops);
        UserChatData.showStopSlider = false; // Hide the stop slider
      } else if (UserChatData.showAddressInput) {
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
        addMessage(selectedChat.id, setChats, chatInput.message);


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
        {UserChatData.showInputBar ? (
        <Box className="input-area">
          {UserChatData.showAddressInput ? (
            <AddressBar UserChatData = {UserChatData}/> // Show AddressBar if address input is required
          ) : UserChatData.showStopSlider ? (
            <StopSlider UserChatData = {UserChatData}/> // Show StopSlider if stop input is required
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
        ):(
        <Box className = "input-area"/>
        )}
      </Box>
    </Box>
  );
};

export default ChatPage;
