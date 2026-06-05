import { validateLocation } from './ValidateLocation';
import { getInitialRoute, getFinalRoute } from './getRoute';
import { generateItinerary } from '../ItineraryPage/generateItinerary';
import { calcHotelBudget, calcGasBudget } from './CalcBudget';
import { updateUserData, createChat } from './DatabaseUtils';

/**
 * Extracts the city name from a full address string returned by the backend.
 * The address format is typically: "Street, City, State, ZIP, Country"
 * Falls back to the raw address string if parsing fails.
 */
const extractCity = (fullAddress) => {
  if (!fullAddress) return null;
  const parts = fullAddress.split(',').map((p) => p.trim());
  if (parts.length >= 3) return parts[1];
  if (parts.length >= 2) return parts[0];
  return parts[0] || null;
};

/**
 * Renames the chat in the sidebar once both start and end cities are known.
 */
export const renameChatToRoute = (chatId, startConfirmed, endConfirmed, setChats) => {
  const startCity = extractCity(startConfirmed?.address);
  const endCity = extractCity(endConfirmed?.address);
  if (!startCity || !endCity) return;
  const newTitle = `Trip to ${endCity}`;
  setChats((prevChats) =>
    prevChats.map((chat) => (chat.id === chatId ? { ...chat, title: newTitle } : chat))
  );
};

// Removes the loading animation
export const removeLoader = (chatId, setChats) => {
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: (chat.messages || []).filter((msg) => !(msg.type === 'loading-chat')),
          }
        : chat
    )
  );
};

// Adds a new message to the chat with optional buttons
export const addMessage = (chatId, setChats, newMessage, sender, buttons = null) => {
  const message =
    newMessage === 'loading'
      ? { type: 'loading-chat' }
      : buttons
        ? { text: newMessage, sender, buttons }
        : typeof newMessage === 'string'
          ? { text: newMessage, sender }
          : { text: String(newMessage), sender };

  setChats((prevChats) => {
    const idx = prevChats.findIndex((chat) => chat.id === chatId);
    // If the chat isn't in state yet (race on first render), create a minimal entry for it
    if (idx === -1) {
      return [...prevChats, { id: chatId, title: 'New Trip', messages: [message] }];
    }
    const prevLength = prevChats[idx]?.messages?.length - 1;
    const prevMessage = prevChats[idx]?.messages?.[prevLength];
    if (!prevMessage || prevMessage.text !== message.text) {
      return prevChats.map((chat) =>
        chat.id === chatId ? { ...chat, messages: [...chat.messages, message] } : chat
      );
    }
    return prevChats;
  });
};

// Updates the last message in the chat
const replacePreviousMessage = (chatId, setChats, newMessage) => {
  setChats((prevChats) =>
    prevChats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: (chat.messages || []).map((message, index, array) =>
              index === array.length - 1 ? { ...message, text: newMessage, buttons: [] } : message
            ),
          }
        : chat
    )
  );
};

/**
 * Direct location input — no method picker, no confirmation dialog.
 * Signals ChatPage to show LocationInput, then waits for startConfirmed/endConfirmed to be set.
 * ChatPage handles the actual validateLocation call via onSubmit / onGeolocate callbacks.
 */
export async function inputLocationDirect(chatId, setChats, setChatInput, chatInput, UserChatData) {
  // Signal ChatPage to show the LocationInput component
  UserChatData.showInputBar = true;
  UserChatData.action = 'Location Input';
  // Force a re-render: update chatInput with a distinct value so React sees a state change
  setChatInput({ name: 'Location Input', message: '' });
  // Also prod setChats so the input bar appears even if setChatInput batches
  setChats((prev) => [...prev]);

  const isEnd = UserChatData.locationType === 'end';
  await new Promise((resolve) => {
    const interval = setInterval(() => {
      const confirmed = isEnd ? UserChatData.endConfirmed : UserChatData.startConfirmed;
      if (confirmed) {
        UserChatData.action = null;
        UserChatData.showInputBar = false;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });
}

export async function handlePromptCarInfo(chatId, setChats, UserChatData) {
  addMessage(
    chatId,
    setChats,
    'The next step in creating your budget is getting an estimated gas cost. Please enter the year, make and model of the vehicle you plan to use. (e.g. 2020 Mazda CX-3)',
    'bot'
  );
  UserChatData.action = 'Car Details';
  UserChatData.showInputBar = true;

  await new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!UserChatData.showInputBar) {
        UserChatData.action = null;
        clearInterval(interval);
        resolve();
      }
    }, 100);
  });

  UserChatData = await calcGasBudget(
    UserChatData.initial['distance'],
    UserChatData.carDetails[0],
    UserChatData.carDetails[1],
    UserChatData.carDetails[2],
    UserChatData.chatId,
    setChats,
    UserChatData
  );
}

// Main Workflow
export const startWorkFlow = async (
  setChats,
  chatId,
  setChatInput,
  chatInput,
  UserChatData,
  ChatLogsData,
  chatsRef,
  access_token,
  setCurrentStep,
  getTripStep
) => {
  const syncStep = () => {
    if (setCurrentStep && getTripStep) setCurrentStep(getTripStep(UserChatData));
  };

  console.log('Starting a workflow');
  UserChatData.workflowStarted = true;
  let preFetchedFinalRoute = null;

  if (!UserChatData.showStopSlider && !UserChatData.startConfirmed) {
    // Checkpoint 1: Enter start location
    UserChatData.showInputBar = false;
    addMessage(chatId, setChats, 'Where are you starting from?', 'bot');

    await inputLocationDirect(chatId, setChats, setChatInput, chatInput, UserChatData);

    addMessage(chatId, setChats, `Starting from: ${UserChatData.startConfirmed.address}`, 'bot');
    syncStep();

    addMessage(chatId, setChats, 'loading', 'bot');
    await updateUserData(access_token, UserChatData, chatsRef.current);
    removeLoader(chatId, setChats);
  }

  if (!UserChatData.endConfirmed && !UserChatData.initial) {
    // Checkpoint 2: Enter end location
    addMessage(chatId, setChats, 'Where are you headed?', 'bot');
    UserChatData.locationType = 'end';

    await inputLocationDirect(chatId, setChats, setChatInput, chatInput, UserChatData);

    addMessage(chatId, setChats, `Destination: ${UserChatData.endConfirmed.address}`, 'bot');
    syncStep();

    renameChatToRoute(chatId, UserChatData.startConfirmed, UserChatData.endConfirmed, setChats);

    const currentChats = chatsRef.current;
    const chatLog = currentChats.find((c) => c.id === chatId);
    if (chatLog) {
      await createChat(access_token, UserChatData, chatLog);
    }

    addMessage(chatId, setChats, 'loading', 'bot');
    UserChatData.initial = await getInitialRoute(
      UserChatData.startConfirmed['latitude'],
      UserChatData.startConfirmed['longitude'],
      UserChatData.endConfirmed['latitude'],
      UserChatData.endConfirmed['longitude']
    );
    syncStep();

    await updateUserData(access_token, UserChatData, chatsRef.current);
    removeLoader(chatId, setChats);

    // Checkpoint 3: How many attractions?
    addMessage(chatId, setChats, 'How many attractions would you like to stop at?', 'bot');
    UserChatData.showInputBar = true;
    UserChatData.showStopSlider = true;
    syncStep();
  }

  if (UserChatData.showInputBar && UserChatData.showStopSlider) {
    // Checkpoint 3 cont: wait for stops input
    await new Promise((resolve) => {
      const interval = setInterval(() => {
        if (!UserChatData.showStopSlider) {
          clearInterval(interval);
          resolve();
        }
      }, 100);
    });
    UserChatData.showInputBar = false;

    addMessage(chatId, setChats, 'loading', 'bot');
    await updateUserData(access_token, UserChatData, chatsRef.current);
    removeLoader(chatId, setChats);
  }

  if (UserChatData.initial && !UserChatData.route) {
    // Checkpoint 4: Budget
    UserChatData.hotelBudget = await calcHotelBudget(
      UserChatData.initial['duration'],
      UserChatData.stops
    );
    if (UserChatData.hotelBudget) {
      addMessage(
        chatId,
        setChats,
        `We estimate your minimum hotel cost to be $${UserChatData.hotelBudget}. Would you like to increase this budget?`,
        'bot'
      );
      UserChatData.showInputBar = true;
      UserChatData.showBudgetSlider = true;

      await new Promise((resolve) => {
        const interval = setInterval(() => {
          if (!UserChatData.showBudgetSlider) {
            clearInterval(interval);
            resolve();
          }
        }, 100);
      });
    }

    preFetchedFinalRoute = getFinalRoute(
      UserChatData.initial,
      UserChatData.hotelBudget,
      UserChatData.stops
    ).catch((error) => {
      console.error('Background final route failed:', error);
      return null;
    });

    await handlePromptCarInfo(chatId, setChats, UserChatData);

    UserChatData.budget = UserChatData.hotelBudget + UserChatData.carBudget;
    addMessage(
      chatId,
      setChats,
      `In total, we estimate your budget to be $${UserChatData.budget}:\nHotel Budget: $${UserChatData.hotelBudget}\nGas Budget: $${UserChatData.carBudget}`,
      'bot'
    );

    addMessage(chatId, setChats, 'loading', 'bot');
    await updateUserData(access_token, UserChatData, chatsRef.current);
    removeLoader(chatId, setChats);
  }

  if (!UserChatData.route && UserChatData.initial) {
    // Checkpoint 5: Generate final route
    addMessage(chatId, setChats, 'loading', 'bot');

    if (preFetchedFinalRoute) {
      UserChatData.route = await preFetchedFinalRoute;
    } else {
      UserChatData.route = await getFinalRoute(
        UserChatData.initial,
        UserChatData.hotelBudget,
        UserChatData.stops
      );
    }
    syncStep();

    await updateUserData(access_token, UserChatData, chatsRef.current);
    removeLoader(chatId, setChats);
  }

  if (UserChatData.route && !UserChatData.itinerary) {
    // Checkpoint 6: Itinerary
    addMessage(chatId, setChats, 'loading', 'bot');
    const itineraryData = await generateItinerary(UserChatData.route);
    const finalMessageText = `Successfully generated your trip! Based on hotel and gas it should cost $${UserChatData.route['cost'] + UserChatData.carBudget}. Click on the Map and Itinerary buttons to view the details.`;

    UserChatData.itinerary = itineraryData;
    UserChatData.isComplete = true;
    syncStep();

    removeLoader(chatId, setChats);
    addMessage(chatId, setChats, finalMessageText, 'bot');

    const chatIndex = ChatLogsData.chatdata.findIndex((c) => c.chatId === UserChatData.chatId);
    if (chatIndex !== -1) {
      ChatLogsData.chatdata[chatIndex] = UserChatData;
    }
    await updateUserData(access_token, UserChatData, chatsRef.current);
  } else if (!UserChatData.route) {
    removeLoader(chatId, setChats);
    addMessage(UserChatData.chatId, setChats, 'Error creating route. Please try again.', 'bot');

    UserChatData.action = null;
    UserChatData.locationType = 'start';
    UserChatData.endConfirmed = null;
    UserChatData.startConfirmed = null;
    UserChatData.initial = null;
    UserChatData.budget = null;

    await startWorkFlow(
      setChats,
      UserChatData.chatId,
      setChatInput,
      chatInput,
      UserChatData,
      ChatLogsData,
      chatsRef,
      access_token,
      setCurrentStep,
      getTripStep
    );

    addMessage(chatId, setChats, 'loading', 'bot');
    await updateUserData(access_token, UserChatData, chatsRef.current);
    removeLoader(chatId, setChats);
  }
};
