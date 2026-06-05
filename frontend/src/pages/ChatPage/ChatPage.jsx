import { useState, useRef, useEffect, useContext, useMemo } from 'react';
import { Box, Button, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import { UserDataContext } from '../../states/UserDataContext';
import { ring } from 'ldrs';
import ThemedTooltip from '../../components/ThemedTooltip';
import ItineraryButton from '../../components/buttons/ItineraryButton';
import MapButton from '../../components/buttons/MapButton';
import TripSearch from './TripSearch';
import LocationInput from './LocationInput';
import StopSlider from './InputStops';
import BudgetSlider from './InputBudget';
import CarInputBar from './InputCar';
import { useTripWorkflow, stepToProgress, renameChatToRoute } from './useTripWorkflow';
import { deleteChat, createChat, initializeUserData } from './DatabaseUtils';
import './ChatPage.css';

ring.register('loading-chat');

// ── WorkflowPanel: isolated component so `key` can reset the workflow hook ──
const WorkflowPanel = ({
  chatId,
  setChats,
  setCurrentStep,
  chatsRef,
  accessToken,
  ChatLogsData,
  activeMessages,
  chatEndRef,
  savedData,
}) => {
  const { step, inputMode, locationVariant, submit, route, itinerary, hotelBudget } =
    useTripWorkflow({
      chatId,
      setChats,
      setCurrentStep,
      savedData,
      chatsRef,
      accessToken,
      ChatLogsData,
    });

  const handleLocationSubmit = (text) =>
    submit(locationVariant === 'start' ? 'start_text' : 'end_text', text);
  const handleLocationGeolocate = (coords) =>
    submit(locationVariant === 'start' ? 'start_coords' : 'end_coords', coords);
  const handleStopsSubmit = (n) => submit('stops', n);

  const [budgetValue, setBudgetValue] = useState(hotelBudget);
  const handleBudgetSubmit = () => submit('budget', budgetValue);

  const [carInputValue, setCarInputValue] = useState(['', '', '']);
  const handleCarSubmit = () => {
    if (carInputValue.some((v) => !v.trim())) return;
    submit('car', carInputValue);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (inputMode === 'budget') handleBudgetSubmit();
      else if (inputMode === 'car') handleCarSubmit();
    }
  };

  const currentProgress = stepToProgress(step);

  return (
    <>
      {/* Nav buttons driven by workflow state */}
      <Box className="fab-group fab-group--bottom">
        <MapButton route={route} currentStep={currentProgress} />
        <ItineraryButton itinerary={itinerary} currentStep={currentProgress} />
      </Box>

      <Box className="main-content">
        <Box className="chat-box">
          <Box className="chat-messages">
            {activeMessages.map((message, index) => {
              if (message.type === 'loading-chat') {
                return (
                  <Box key={index} className="message-container">
                    <loading-chat size="30" color="black" />
                  </Box>
                );
              }
              if (message.buttons?.length > 0) {
                return (
                  <Box key={index} className="message-container user">
                    <Box className="message user">
                      <Typography variant="body1">{message.text}</Typography>
                    </Box>
                    <Box className="button-container">
                      {message.buttons.map((btn, bi) => (
                        <Button
                          key={bi}
                          className="chat-buttons"
                          variant="contained"
                          color="primary"
                        >
                          {btn.label}
                        </Button>
                      ))}
                    </Box>
                  </Box>
                );
              }
              if (message.text != null) {
                return (
                  <Box key={index} className={`message ${message.sender}`}>
                    <Typography variant="body1">{message.text}</Typography>
                  </Box>
                );
              }
              return null;
            })}

            {/* Floating input — renders inline at the bottom of the message list */}
            {inputMode !== 'none' && (
              <Box className="inline-input-area">
                {inputMode === 'location' ? (
                  <LocationInput
                    placeholder={
                      locationVariant === 'start'
                        ? 'Enter your starting city or address…'
                        : 'Enter your destination city or address…'
                    }
                    onSubmit={handleLocationSubmit}
                    onGeolocate={handleLocationGeolocate}
                  />
                ) : inputMode === 'stops' ? (
                  <StopSlider onSelect={handleStopsSubmit} />
                ) : inputMode === 'budget' ? (
                  <Box className="inline-input-row">
                    <BudgetSlider
                      UserChatData={{ hotelBudget }}
                      handleKeyDown={handleKeyDown}
                      onValueChange={setBudgetValue}
                    />
                    <Button
                      variant="contained"
                      className="send-button"
                      onClick={handleBudgetSubmit}
                    >
                      Confirm
                    </Button>
                  </Box>
                ) : inputMode === 'car' ? (
                  <Box className="inline-input-row">
                    <CarInputBar handleKeyDown={handleKeyDown} onValueChange={setCarInputValue} />
                    <Button variant="contained" className="send-button" onClick={handleCarSubmit}>
                      Send
                    </Button>
                  </Box>
                ) : null}
              </Box>
            )}

            <div ref={chatEndRef} />
          </Box>
        </Box>
      </Box>
    </>
  );
};

// eslint-disable-next-line react/prop-types
WorkflowPanel.displayName = 'WorkflowPanel';

const ChatPage = () => {
  const { UserData, setUserData, chats, setChats, setCurrentStep } = useContext(UserDataContext);
  const ChatLogsData = UserData.chatlogs;
  const accessToken = sessionStorage.getItem('accessToken');

  const initialMessage = useMemo(
    () => [
      {
        text: "Hello! I'm JourneyGenie. Let's plan your road trip!",
        sender: 'bot',
      },
    ],
    []
  );

  // Fresh trip scaffolded immediately — no waiting for DB
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const freshChatData = useMemo(() => ChatLogsData.createChatData(1), []);
  const freshChat = useMemo(
    () => ({ id: 1, title: 'New Trip', messages: initialMessage }),
    [initialMessage]
  );

  const chatsRef = useRef([freshChat]);

  // Restore last selected chat id from sessionStorage so navigation away/back works
  const storedId = parseInt(sessionStorage.getItem('selectedChatId') ?? '1', 10);
  const [selectedChatId, setSelectedChatId] = useState(storedId);
  const selectedChatIdRef = useRef(storedId);

  // Keep sessionStorage in sync whenever selected chat changes
  const setSelectedChatIdPersisted = (id) => {
    sessionStorage.setItem('selectedChatId', String(id));
    setSelectedChatId(id);
    selectedChatIdRef.current = id;
    ChatLogsData.currentId = id; // keep MapPage/ItineraryPage lookup in sync
  };

  // Incrementing this key unmounts/remounts WorkflowPanel, resetting the hook
  const [workflowKey, setWorkflowKey] = useState(0);
  // savedData: initialize synchronously from context so WorkflowPanel gets it on first render.
  // On first load chats is empty → null (fresh trip). On remount after navigation,
  // chats context is already populated → restore the selected chat's data so the
  // workflow resumes at 'done' rather than restarting from scratch.
  const [savedData, setSavedData] = useState(() => {
    const contextChats = chats; // captured at construction time
    if (contextChats.length === 0) return null;
    return ChatLogsData.getChatDataById(storedId) ?? null;
  });

  const [isFetchingChats, setIsFetchingChats] = useState(true);
  const [searchOpen, setSearchOpen] = useState(false);
  const chatEndRef = useRef(null);

  // Live messages always read from `chats` — never a stale snapshot
  const activeMessages = chats.find((c) => c.id === selectedChatId)?.messages ?? initialMessage;

  // Seed chats state on mount
  useEffect(() => {
    setChats((prev) => (prev.length === 0 ? [freshChat] : prev));
    // Re-sync chatsRef from context on every mount (covers navigation remounts)
    chatsRef.current = chats.length > 0 ? chats : [freshChat];
    // Keep currentId in sync so MapPage/ItineraryPage can find the right chat
    ChatLogsData.currentId = storedId;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ⌘K / Ctrl+K
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Background DB fetch — only runs on first mount (chats context is empty)
  useEffect(() => {
    const fetchData = async () => {
      // If chats context already has data, this is a remount after navigation — skip the fetch.
      // The context already holds the correct state from the previous mount.
      if (chats.length > 0) {
        setIsFetchingChats(false);
        return;
      }
      setIsFetchingChats(true);
      try {
        const prevChats = await initializeUserData(accessToken);
        if (prevChats?.chats?.length > 0) {
          const completeChatData = prevChats.UserData.chatlogs.chatdata.filter(
            (cd) => cd.endConfirmed
          );
          const incompleteChatData = prevChats.UserData.chatlogs.chatdata.filter(
            (cd) => !cd.endConfirmed
          );
          for (const cd of incompleteChatData) {
            deleteChat(accessToken, cd.chatId).catch(() => {});
          }
          const completeChats = prevChats.chats.filter((c) =>
            completeChatData.some((cd) => cd.chatId === c.id)
          );
          prevChats.UserData.chatlogs.chatdata = completeChatData;
          for (const cd of prevChats.UserData.chatlogs.chatdata) {
            cd.workflowStarted = false;
          }

          if (completeChats.length > 0) {
            setUserData(prevChats.UserData);
            const maxOldId = completeChats.reduce((max, c) => Math.max(max, c.id), 0);
            const newId = maxOldId + 1;
            freshChatData.chatId = newId;
            const updatedFreshChat = { ...freshChat, id: newId, title: 'New Trip' };
            prevChats.UserData.chatlogs.createChatData(newId);
            setChats([...completeChats, updatedFreshChat]);
            chatsRef.current = [...completeChats, updatedFreshChat];

            const restoredId = selectedChatIdRef.current;
            if (restoredId === 1) {
              // Was on a fresh trip — keep on the new fresh trip
              setSelectedChatIdPersisted(newId);
            } else {
              // Was on a completed trip — restore its savedData so workflow resumes at 'done'
              const restoredData = prevChats.UserData.chatlogs.getChatDataById(restoredId);
              if (restoredData) setSavedData(restoredData);
              setWorkflowKey((k) => k + 1); // remount WorkflowPanel with the restored data
            }
          }
        }
      } catch {
        // silently continue with fresh trip
      } finally {
        setIsFetchingChats(false);
      }
    };
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Rename loaded trips that have both endpoints but a generic title
  useEffect(() => {
    if (chats.length === 0) return;
    chats.forEach((chat) => {
      if (!chat.title.startsWith('Trip to')) {
        const chatData = ChatLogsData.getChatDataById(chat.id);
        if (chatData?.startConfirmed && chatData?.endConfirmed) {
          renameChatToRoute(chat.id, chatData.startConfirmed, chatData.endConfirmed, setChats);
        }
      }
    });
  }, [chats.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    chatsRef.current = chats;
  }, [chats]);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeMessages?.length]);

  // ── Chat / trip management ────────────────────────────────────────────────

  const handleSelectChat = (chat) => {
    const chatData = ChatLogsData.getChatDataById(chat.id);
    setSavedData(chatData ?? null);
    setSelectedChatIdPersisted(chat.id);
    ChatLogsData.currentId = chat.id;
    setWorkflowKey((k) => k + 1); // remount WorkflowPanel with restored data
  };

  const handleNewChat = () => {
    // A trip is "virgin" if the user hasn't sent any messages yet
    const isVirgin = (chat) =>
      chat.title === 'New Trip' && !chat.messages?.some((m) => m.sender === 'user');

    // If any trip in the list is already virgin, switch to it
    const existingVirgin = chatsRef.current.find(isVirgin);
    if (existingVirgin) {
      setSavedData(null);
      setSelectedChatIdPersisted(existingVirgin.id);
      setWorkflowKey((k) => k + 1);
      return;
    }

    const maxId = chatsRef.current.reduce((max, c) => Math.max(max, c.id), 0);
    const newId = maxId + 1;
    ChatLogsData.createChatData(newId);
    const newChat = { id: newId, title: 'New Trip', messages: initialMessage };
    setChats((prev) => [...prev, newChat]);
    chatsRef.current = [...chatsRef.current, newChat];
    setSavedData(null);
    setSelectedChatIdPersisted(newId);
    setWorkflowKey((k) => k + 1);
  };

  const handleDeleteChat = async (chatId) => {
    const remaining = chatsRef.current.filter((c) => c.id !== chatId);
    ChatLogsData.removeChatData(chatId);

    if (remaining.length === 0) {
      const newId = 1;
      ChatLogsData.createChatData(newId);
      const newChat = { id: newId, title: 'New Trip', messages: initialMessage };
      setChats([newChat]);
      chatsRef.current = [newChat];
      setSelectedChatIdPersisted(newId);
      setWorkflowKey((k) => k + 1);
      await deleteChat(accessToken, chatId);
      // No createChat here — the workflow will create the row when the user confirms their destination
    } else {
      setChats(remaining);
      chatsRef.current = remaining;
      await deleteChat(accessToken, chatId);
      if (selectedChatIdRef.current === chatId) {
        const next = remaining[remaining.length - 1];
        setSelectedChatIdPersisted(next.id);
        setWorkflowKey((k) => k + 1);
      }
    }
  };

  return (
    <Box className="page-container">
      {searchOpen && (
        <TripSearch
          chats={chats}
          selectedChatId={selectedChatId}
          isFetchingChats={isFetchingChats}
          getChatInfo={(cid) => {
            const cd = ChatLogsData.getChatDataById(cid);
            const s = stepToProgress(
              cd?.isComplete
                ? 'done'
                : cd?.route
                  ? 'done'
                  : cd?.initial
                    ? 'fetching_budget'
                    : cd?.endConfirmed
                      ? 'fetching_initial'
                      : cd?.startConfirmed
                        ? 'end_input'
                        : 'start_input'
            );
            const city = (addr) => {
              if (!addr) return null;
              const p = addr.split(',').map((x) => x.trim());
              return p.length >= 3 ? p[1] : (p[0] ?? null);
            };
            return {
              step: s,
              startCity: cd?.startConfirmed ? city(cd.startConfirmed.address) : null,
              endCity: cd?.endConfirmed ? city(cd.endConfirmed.address) : null,
            };
          }}
          onSelect={(chat) => {
            handleSelectChat(chat);
            setSearchOpen(false);
          }}
          onDelete={handleDeleteChat}
          onClose={() => setSearchOpen(false)}
        />
      )}

      {/* Trip management buttons — top-left (below header) */}
      <Box className="fab-group fab-group--top">
        <ThemedTooltip title="New trip" placement="right" arrow>
          <Box className="fab fab--new" onClick={handleNewChat} role="button" aria-label="New trip">
            <AddIcon className="fab-icon" />
          </Box>
        </ThemedTooltip>
        <ThemedTooltip title="Search trips  ⌘K" placement="right" arrow>
          <Box
            className="fab"
            onClick={() => setSearchOpen(true)}
            role="button"
            aria-label="Search trips"
          >
            <SearchIcon className="fab-icon" />
          </Box>
        </ThemedTooltip>
      </Box>

      {/* WorkflowPanel: keyed so bumping workflowKey resets the hook */}
      <WorkflowPanel
        key={workflowKey}
        chatId={selectedChatId}
        setChats={setChats}
        setCurrentStep={setCurrentStep}
        chatsRef={chatsRef}
        accessToken={accessToken}
        ChatLogsData={ChatLogsData}
        activeMessages={activeMessages}
        chatEndRef={chatEndRef}
        savedData={savedData}
      />
    </Box>
  );
};

export default ChatPage;
