import { useState, useRef, useEffect, useContext, useMemo } from 'react';
import { Box, TextField, Button, Typography } from '@mui/material';
import customTheme from '../../components/Theme';
import ItineraryButton from '../../components/buttons/ItineraryButton';
import MapButton from '../../components/buttons/MapButton';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import { startWorkFlow, addMessage } from './startWorkFlow';
import CarInputBar from './InputCar';
import BudgetSlider from './InputBudget';
import StopSlider from './InputStops';
import AddressBar from './InputAddress';
import { UserDataContext } from '../../states/UserDataContext';
import { validateLocation } from './ValidateLocation';
import { ring } from 'ldrs'; //Loading Animation
import './ChatPage.css';
import { createChat, deleteChat, initializeUserData } from './DatabaseUtils';

ring.register('loading-chat'); //Define the loading animation

const ChatPage = () => {
  // Retrieve the global instance of UserData and getUserData function
  const { UserData, setUserData, chats, setChats } = useContext(UserDataContext);
  // Grab the chat logs
  const ChatLogsData = UserData.chatlogs;
  // State to track current chats data
  const initialUserChatData =
    ChatLogsData?.chatdata?.length > 0
      ? ChatLogsData.getChatDataById(ChatLogsData.currentId) || ChatLogsData.chatdata[0]
      : ChatLogsData.createChatData(1);
  const [UserChatData, setUserChatData] = useState(initialUserChatData);

  // Initial message displayed in a new chat
  const initialMessage = useMemo(
    () => [
      {
        text: "Hello there! I’m MyRoadtrip, and I’m excited to help you with your trip planning. To get started, could you please tell me how you would like to enter your trip's starting point?",
        sender: 'bot', // either bot or user
      },
    ],
    []
  );

  //Retrieve the authorization token
  const accessToken = sessionStorage.getItem('accessToken');

  // State to manage the list of chats
  const chatsRef = useRef(chats);

  // State to manage the currently selected chat
  const [selectedChat, setSelectedChat] = useState(null);

  // State to manage the chat input (message box)
  const [chatInput, setChatInput] = useState({
    name: 'Type a Message',
    message: '',
  });

  // Ref to scroll the chat to the bottom
  const chatEndRef = useRef(null);

  // State to track workflow status
  const [workflowStarted, setWorkflowStarted] = useState(UserChatData?.workflowStarted || false);

  // State to track if chats are currently being fetched from the database
  const [isFetchingChats, setIsFetchingChats] = useState(chats.length === 0);

  // Trigger workflow when a chat is selected, ensuring it only starts once
  useEffect(() => {
    setWorkflowStarted(UserChatData?.workflowStarted || false); // ensure the accurate workflowStarted is set
    if (selectedChat && !UserChatData?.workflowStarted && UserChatData) {
      UserChatData.workflowStarted = true;
      if (UserChatData.isComplete) {
        // Chat is finished, bypass workflow entirely
        setWorkflowStarted(true);
      } else {
        // Start the workflow for the newly selected chat
        startWorkFlow(
          setChats,
          selectedChat.id,
          setChatInput,
          chatInput,
          UserChatData,
          ChatLogsData,
          chatsRef,
          accessToken
        );
        // Mark the workflow as started
        setWorkflowStarted(true);
      }
    }
  }, [selectedChat, workflowStarted, UserChatData, ChatLogsData, accessToken, chatInput, setChats]);

  // Automatically load chats from Database or create a chat during initial mount TODO change to be load from the database and if there isn't entries then make one
  useEffect(() => {
    const fetchData = async () => {
      if (chats.length === 0) {
        setIsFetchingChats(true);
        try {
          const prevChats = await initializeUserData(accessToken);
          console.log(prevChats);
          if (prevChats && prevChats.chats && prevChats.chats.length > 0) {
            setChats(prevChats['chats']);
            setUserData(prevChats['UserData']);
            const currentId = prevChats['UserData'].chatlogs.currentId;
            setSelectedChat(prevChats['chats'].find((chat) => chat.id === currentId));

            const fetchedChatData =
              prevChats['UserData'].chatlogs.chatdata.find((c) => c.chatId === currentId) ||
              prevChats['UserData'].chatlogs.chatdata[0];
            setUserChatData(fetchedChatData);
            for (let i = 0; i < prevChats['UserData'].chatlogs.chatdata.length; i++) {
              prevChats['UserData'].chatlogs.chatdata[i].workflowStarted = false; // Reset the workflows for all fetched chats
            }
          } else {
            const initialChats = [
              {
                id: 1,
                title: 'Chat 1',
                messages: initialMessage,
              },
            ];
            console.log('Initialized chats with default:', initialChats);
            const NewChatData = ChatLogsData.createChatData(1);
            setUserChatData(NewChatData);
            setChats(initialChats);
            chatsRef.current = initialChats;
            setSelectedChat(initialChats[0]);
            setWorkflowStarted(false);
            await createChat(accessToken, NewChatData, initialChats[0]);

            for (let i = 0; i < ChatLogsData.chatdata.length; i++) {
              ChatLogsData.chatdata[i].workflowStarted = false; // Reset the workflows for all saved chats on mount
            }
          }
        } catch (error) {
          console.log('Error loading data from database');
        } finally {
          setIsFetchingChats(false);
        }
      } else {
        setIsFetchingChats(false);
      }
    };

    fetchData();
  }, [
    ChatLogsData,
    UserChatData,
    accessToken,
    chats.length,
    initialMessage,
    setChats,
    setUserData,
  ]);

  // Automatically setSelected chat on initial mount
  useEffect(() => {
    if (chats.length > 0) {
      const idx = chats.findIndex((chat) => chat.id === UserChatData.chatId);
      if (idx >= 0 && idx < chats.length) {
        setSelectedChat(chats[idx]);
      } else {
        console.error('Invalid chat ID:', UserChatData.chatId);
      }
    }
  }, [chats, UserChatData.chatId]);

  useEffect(() => {
    chatsRef.current = chats;
  }, [chats]);

  // Handle chat selection from the sidebar
  const handleSelectChat = (chat) => {
    const selectedChatData = ChatLogsData.getChatDataById(chat.id);
    setSelectedChat({ ...chat, ...selectedChatData });
    setUserChatData(selectedChatData);
    ChatLogsData.currentId = chat.id;
  };

  // Scroll to the bottom of the chat when a new chat is selected
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [selectedChat]);

  // Handle the sending of messages in the chat
  const handleSendMessage = async () => {
    if (selectedChat) {
      if (UserChatData.showStopSlider) {
        // Handle input of the number of user stops
        addMessage(selectedChat.id, setChats, UserChatData.stops, 'user');
        UserChatData.showStopSlider = false; // Hide the stop slider
      } else if (UserChatData.showBudgetSlider) {
        addMessage(selectedChat.id, setChats, `$${UserChatData.hotelBudget}`, 'user'); //Display the hotel budget the user input
        UserChatData.showBudgetSlider = false; // Hide the budget slider
      } else if (UserChatData.action === 'Car Details') {
        //Store the car details if action is "Car Details"
        // Handle car input message
        const carDetails = UserChatData.carDetails || ['', '', ''];

        addMessage(
          selectedChat.id,
          setChats,
          `${carDetails[0]} ${carDetails[1]} ${carDetails[2]}`,
          'user'
        );
        UserChatData.showInputBar = false;
      } else if (UserChatData.showAddressInput) {
        // Handle address input message
        const address =
          UserChatData.locationType === 'start'
            ? UserChatData.startAddress
            : UserChatData.endAddress;

        addMessage(
          selectedChat.id,
          setChats,
          `${address[0]} ${address[1]} ${address[2]} ${address[3]}`,
          'user'
        );
        UserChatData.showInputBar = false;
        UserChatData.showAddressInput = false;

        // Confirm the address that the user inputted
        if (UserChatData.locationType === 'start') {
          UserChatData.startConfirmed = await validateLocation(
            `${address[0]} ${address[1]} ${address[2]} ${address[3]}`,
            false,
            UserChatData,
            setChats,
            setChatInput,
            chatInput
          );
        } else {
          UserChatData.endConfirmed = await validateLocation(
            `${address[0]} ${address[1]} ${address[2]} ${address[3]}`,
            false,
            UserChatData,
            setChats,
            setChatInput,
            chatInput
          );
        }
      } else if (chatInput.message.trim() !== '') {
        // Handle regular message submission
        addMessage(selectedChat.id, setChats, chatInput.message, 'user');

        // Store the message if action is "City Name"
        if (UserChatData.action === 'City Name') {
          if (UserChatData.locationType === 'start') {
            UserChatData.startAddress[1] = chatInput.message;
            UserChatData.startConfirmed = await validateLocation(
              UserChatData.startAddress[1],
              false,
              UserChatData,
              setChats,
              setChatInput,
              chatInput
            );
          } else if (UserChatData.locationType === 'end') {
            UserChatData.endAddress[1] = chatInput.message;
            UserChatData.endConfirmed = await validateLocation(
              UserChatData.endAddress[1],
              false,
              UserChatData,
              setChats,
              setChatInput,
              chatInput
            );
          }
        }

        //Hide the input bar
        UserChatData.showInputBar = false;

        // Reset the input field
        setChatInput({
          ...chatInput,
          message: '',
        });
      }
    }
  };

  const handleNewChat = async () => {
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
    setWorkflowStarted(false);

    await createChat(accessToken, NewChatData, newChat);
    console.log('Stored new chat', NewChatData, newChat);
  };

  // Handle the deletion of a chat
  const handleDeleteChat = async (chatId) => {
    const remainingChats = chatsRef.current.filter((chat) => chat.id !== chatId);
    ChatLogsData.removeChatData(chatId);

    if (remainingChats.length === 0) {
      // If the user deleted their last chat, instantly scaffold a fresh one
      const newChatId = 1;
      const NewChatData = ChatLogsData.createChatData(newChatId);
      const newChat = {
        id: newChatId,
        title: `Chat ${newChatId}`,
        messages: initialMessage,
      };
      setUserChatData(NewChatData);
      setChats([newChat]);
      chatsRef.current = [newChat];
      setSelectedChat(newChat);
      setWorkflowStarted(false);
      await deleteChat(accessToken, chatId);
      await createChat(accessToken, NewChatData, newChat);
    } else {
      setChats(remainingChats);
      await deleteChat(accessToken, chatId);
      if (selectedChat?.id === chatId) {
        setSelectedChat(null); // Deselect the chat if it's the one being deleted
      }
    }
  };

  // Handle the pressing of the "Enter" key to send a message
  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
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
          {isFetchingChats ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
              <loading-chat size="30" color="black"></loading-chat>
            </Box>
          ) : (
            chats.map((chat) => (
              <Box
                key={chat.id}
                className={`chat-item ${selectedChat?.id === chat.id ? 'selected' : ''}`}
                onClick={() => handleSelectChat(chat)}
                sx={{
                  bgcolor:
                    selectedChat?.id === chat.id
                      ? customTheme.palette.white.dark
                      : customTheme.palette.white.main,
                  color: selectedChat?.id === chat.id ? 'white' : 'text.primary',
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
            ))
          )}
        </Box>

        {/* Sidebar bottom buttons for map and itinerary */}
        <Box className="sidebar-bottom">
          <Box sx={{ mb: -1, width: '100%' }}>
            <MapButton route={UserChatData.route} />
          </Box>
          <Box sx={{ mb: -1, width: '100%' }}>
            <ItineraryButton itinerary={UserChatData.itinerary} />
          </Box>
        </Box>
      </Box>

      {/* Main content area displaying the chat messages */}
      <Box className="main-content">
        {/* Chat box area */}
        <Box className="chat-box">
          {isFetchingChats ? (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100%',
              }}
            >
              <loading-chat size="50" color="black"></loading-chat>
              <Typography variant="body1" sx={{ mt: 2 }}>
                Loading your chats...
              </Typography>
            </Box>
          ) : selectedChat ? (
            <Box className="chat-messages">
              {/* Display messages in the selected chat */}
              {selectedChat.messages.map((message, index) => {
                if (Object.keys(message).length === 2 || message.buttons === null) {
                  // Render simple text messages
                  return (
                    <Box key={index} className={`message ${message.sender}`}>
                      <Typography variant="body1">{message.text}</Typography>
                    </Box>
                  );
                } else if (message.buttons) {
                  // Render messages that contain both text and buttons
                  return (
                    <Box key={index} className="message-container user">
                      {/* Render the message text */}
                      <Box className="message user">
                        <Typography variant="body1">{message.text}</Typography>
                      </Box>
                      {/* Render buttons associated with the message */}
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
                  );
                } else if (message.type === 'loading-chat') {
                  // Render a React component if 'message' is a React element
                  return (
                    <Box key={index} className="message-container">
                      {/* Dynamically create and render the React component */}
                      <loading-chat size="30" color="black"></loading-chat>
                    </Box>
                  );
                }
                // Return null if none of the above conditions are met
                return null;
              })}
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
              <AddressBar UserChatData={UserChatData} handleKeyDown={handleKeyDown} /> // Show AddressBar if address input is required
            ) : UserChatData.showStopSlider ? (
              <StopSlider UserChatData={UserChatData} handleKeyDown={handleKeyDown} /> // Show StopSlider if stop input is required
            ) : UserChatData.showBudgetSlider ? (
              <BudgetSlider UserChatData={UserChatData} handleKeyDown={handleKeyDown} /> // Show BudgetSlider if budget input is required
            ) : UserChatData.action === 'Car Details' ? (
              <CarInputBar UserChatData={UserChatData} handleKeyDown={handleKeyDown} /> // Show Car Input Bar if car input is required
            ) : (
              <TextField
                label={chatInput.name}
                placeholder={chatInput.name}
                value={chatInput.message}
                onChange={(e) => setChatInput({ ...chatInput, message: e.target.value })}
                onKeyDown={handleKeyDown}
                fullWidth
                multiline
                sx={{
                  backgroundColor: customTheme.palette.white.main,
                  borderRadius: '5px',
                }}
              />
            )}
            <Button
              variant="contained"
              color="primary"
              className="send-button"
              onClick={handleSendMessage}
              disabled={!UserChatData.route && UserChatData.budget > 0} // Disable the send button if the initial route
            >
              Send
            </Button>
          </Box>
        ) : (
          <Box className="input-area" />
        )}
      </Box>
    </Box>
  );
};

export default ChatPage;
