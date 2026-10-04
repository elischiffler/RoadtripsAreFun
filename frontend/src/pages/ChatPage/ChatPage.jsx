import { useState, useRef, useEffect, useContext, useMemo, useCallback } from 'react';
import { Box, Button, Typography } from '@mui/material';
import PropTypes from 'prop-types';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import { UserDataContext } from '../../states/UserDataContext';
import TripProgress from './TripProgress';
import ChatMessage from './ChatMessage';
import ThemedTooltip from '../../components/ThemedTooltip';
import ItineraryButton from '../../components/buttons/ItineraryButton';
import MapButton from '../../components/buttons/MapButton';
import TripSearch from './TripSearch';
import ChatInput from './ChatInput';
import { useTripWorkflow, deriveProgress, renameChatToRoute } from './useTripWorkflow';
import { deleteChat, initializeUserData } from './DatabaseUtils';
import { chooseRestoredChatId, forgetAgentChatId, getOrCreateAgentChatId } from './chatSession';
import './ChatPage.css';

// ── WorkflowPanel: isolated component so `key` can reset the workflow hook ──
const WorkflowPanel = ({
  chatId,
  agentChatId,
  setChats,
  setCurrentStep,
  chatsRef,
  accessToken,
  ChatLogsData,
  activeMessages,
  chatEndRef,
  savedData,
  onChatReady,
}) => {
  const { submit, route, itinerary, isLoading, processProgress, pendingLocations } =
    useTripWorkflow({
      chatId,
      agentChatId,
      setChats,
      setCurrentStep,
      savedData,
      chatsRef,
      accessToken,
      ChatLogsData,
      onChatReady,
    });

  const handleChatSubmit = (text) => submit('chat_message', text);

  const currentProgress = deriveProgress({ route });
  const locationSelections = Object.entries(pendingLocations ?? {}).flatMap(([field, pending]) =>
    pending.candidates.length
      ? [{ field, candidateId: pending.candidates[0].id, address: pending.candidates[0].address }]
      : []
  );

  const latestBotIndex = activeMessages.findLastIndex(
    (message) => message.sender === 'bot' && message.text != null
  );

  return (
    <>
      {/* Nav buttons driven by workflow state */}
      <Box className="fab-group fab-group--bottom">
        <MapButton route={route} currentStep={currentProgress} />
        <ItineraryButton itinerary={itinerary} currentStep={currentProgress} />
      </Box>

      <Box className="main-content">
        <Box className="chat-box">
          <Box
            className="chat-messages"
            role="log"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {activeMessages.map((message, index) => {
              if (message.type === 'loading-chat') {
                return (
                  <Box key={index} className="message-container">
                    <TripProgress progress={processProgress} />
                  </Box>
                );
              }
              if (message.buttons?.length > 0) {
                return (
                  <Box key={index} className="message-container user">
                    <Box className="message user">
                      <ChatMessage message={message} />
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
                    <ChatMessage
                      message={message}
                      pendingLocationFields={
                        index === latestBotIndex ? Object.keys(pendingLocations ?? {}) : []
                      }
                    />
                  </Box>
                );
              }
              return null;
            })}

            {Object.entries(pendingLocations ?? {}).map(([field, pending]) => (
              <Box
                key={field}
                role="group"
                aria-label={
                  field === 'start_address' ? 'Confirm starting location' : 'Confirm destination'
                }
                className="message bot"
                sx={{ maxWidth: '100%' }}
              >
                <Typography sx={{ fontWeight: 600 }}>
                  {field === 'start_address' ? 'Starting location' : 'Destination'}
                </Typography>
                {pending.candidates.length ? (
                  <>
                    <Typography>Suggested address: {pending.candidates[0].address}</Typography>
                  </>
                ) : (
                  <Typography>No match found for &quot;{pending.query}&quot;.</Typography>
                )}
              </Box>
            ))}
            {locationSelections.length > 0 && (
              <Box className="message bot">
                <Button
                  variant="text"
                  size="small"
                  className="location-confirm-button"
                  disableRipple
                  aria-label={
                    locationSelections.length > 1
                      ? 'Confirm both locations'
                      : locationSelections[0].field === 'start_address'
                        ? 'Confirm starting location'
                        : 'Confirm destination'
                  }
                  disabled={isLoading}
                  onClick={() => submit('location_confirmations', locationSelections)}
                >
                  {locationSelections.length > 1 ? 'Confirm both locations' : 'Confirm'}
                </Button>
              </Box>
            )}
            {Object.keys(pendingLocations ?? {}).length > 0 && (
              <Typography className="message bot" variant="body2">
                Wrong location? Type a different city or address below.
              </Typography>
            )}
            <div ref={chatEndRef} />
          </Box>

          {/* Persistent free-text agent input — pinned to the bottom so it never
              scrolls away. While a turn is in flight the send button is disabled
              (isLoading) until the agent finishes and the user should type again. */}
          <Box className="inline-input-area">
            <ChatInput onSubmit={handleChatSubmit} disabled={isLoading} />
          </Box>
        </Box>
      </Box>
    </>
  );
};

WorkflowPanel.propTypes = {
  chatId: PropTypes.number.isRequired,
  agentChatId: PropTypes.string.isRequired,
  setChats: PropTypes.func.isRequired,
  setCurrentStep: PropTypes.func.isRequired,
  chatsRef: PropTypes.shape({ current: PropTypes.array }).isRequired,
  accessToken: PropTypes.string,
  ChatLogsData: PropTypes.object.isRequired,
  activeMessages: PropTypes.arrayOf(
    PropTypes.shape({
      text: PropTypes.string,
      sender: PropTypes.string,
      type: PropTypes.string,
      buttons: PropTypes.arrayOf(PropTypes.shape({ label: PropTypes.string })),
    })
  ).isRequired,
  chatEndRef: PropTypes.shape({ current: PropTypes.any }).isRequired,
  savedData: PropTypes.object,
  onChatReady: PropTypes.func.isRequired,
};

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
  const [freshChatData] = useState(
    () => ChatLogsData.getChatDataById(1) ?? ChatLogsData.createChatData(1)
  );
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
  const [loadError, setLoadError] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const chatEndRef = useRef(null);
  // Holds a { id, title, messages } for a new trip that hasn't had its destination confirmed yet.
  // It lives outside `chats` until onChatReady fires so it doesn't appear in the sidebar prematurely.
  const pendingChatRef = useRef(null);

  // ── Agent conversation ids (B2: globally-unique keys) ─────────────────────
  // The integer chat `id` is reused across sessions (maxId+1, reset per load), so
  // it can't safely key the backend's per-chat agent memory. We map each integer
  // chat id to a stable UUID and send THAT as the agent `chatId`, guaranteeing a
  // brand-new chat never inherits a prior chat's trip profile / conversation.
  const agentChatIdMapRef = useRef(new Map());
  const getAgentChatId = useCallback(
    (chatId) =>
      getOrCreateAgentChatId(
        chatId,
        ChatLogsData.getChatDataById(chatId),
        agentChatIdMapRef.current
      ),
    [ChatLogsData]
  );

  // Live messages always read from `chats` — never a stale snapshot
  const activeMessages = chats.find((c) => c.id === selectedChatId)?.messages ?? initialMessage;

  // Seed chats state on mount
  useEffect(() => {
    if (chats.length === 0) {
      setChats([freshChat]);
      pendingChatRef.current = freshChat;
    }
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
    let cancelled = false;
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
        if (cancelled) return;
        if (!prevChats) throw new Error('Chat loading failed');
        if (prevChats) {
          const savedChats = prevChats.chats ?? [];
          if (savedChats.length > 0) {
            for (const cd of prevChats.UserData.chatlogs.chatdata) {
              cd.workflowStarted = false;
            }
            setUserData(prevChats.UserData);
            agentChatIdMapRef.current.clear();
            const maxOldId = savedChats.reduce((max, c) => Math.max(max, c.id), 0);
            const newId = maxOldId + 1;
            freshChatData.chatId = newId;
            const updatedFreshChat = { ...freshChat, id: newId, title: 'New Trip' };
            prevChats.UserData.chatlogs.createChatData(newId);
            // Mark the fresh chat as pending — it won't appear in TripSearch until destination confirmed
            pendingChatRef.current = updatedFreshChat;
            setChats([...savedChats, updatedFreshChat]);
            chatsRef.current = [...savedChats, updatedFreshChat];

            const restoredId = selectedChatIdRef.current;
            const activeId = chooseRestoredChatId(restoredId, savedChats, newId);
            prevChats.UserData.chatlogs.currentId = activeId;
            if (activeId === newId) {
              setSelectedChatIdPersisted(newId);
            } else {
              const restoredData = prevChats.UserData.chatlogs.getChatDataById(restoredId);
              if (restoredData) setSavedData(restoredData);
              setWorkflowKey((k) => k + 1); // remount WorkflowPanel with the restored data
            }
          } else {
            // A stored selection can point to a chat removed in another session.
            forgetAgentChatId(1, agentChatIdMapRef.current);
            setSelectedChatIdPersisted(1);
            setWorkflowKey((k) => k + 1);
          }
        }
      } catch {
        // Do not allocate a reused integer id when saved rows could not be read.
        if (!cancelled) setLoadError(true);
      } finally {
        if (!cancelled) setIsFetchingChats(false);
      }
    };
    fetchData();
    return () => {
      cancelled = true;
    };
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

    // If there's already a pending (unconfirmed) trip, reuse it if still virgin
    if (pendingChatRef.current) {
      const pending = pendingChatRef.current;
      // Already on it and it's still fresh — nothing to do
      if (isVirgin(pending) && pending.id === selectedChatId) return;
      if (isVirgin(pending)) {
        setSavedData(null);
        setSelectedChatIdPersisted(pending.id);
        setWorkflowKey((k) => k + 1);
        return;
      }
    }

    // If any confirmed trip in the list is still virgin, switch to it
    const existingVirgin = chatsRef.current.find(
      (c) => isVirgin(c) && c.id !== (pendingChatRef.current?.id ?? -1)
    );
    if (existingVirgin) {
      setSavedData(null);
      setSelectedChatIdPersisted(existingVirgin.id);
      setWorkflowKey((k) => k + 1);
      return;
    }

    const maxId = Math.max(
      chatsRef.current.reduce((max, c) => Math.max(max, c.id), 0),
      pendingChatRef.current?.id ?? 0
    );
    const newId = maxId + 1;
    // A brand-new chat gets a fresh UUID agent key (see getAgentChatId), so it can
    // never inherit a prior chat's trip profile / conversation.
    ChatLogsData.createChatData(newId);
    const newChat = { id: newId, title: 'New Trip', messages: initialMessage };
    // Add to chats so messages render, but mark as pending so TripSearch hides it
    pendingChatRef.current = newChat;
    setChats((prev) => [...prev, newChat]);
    chatsRef.current = [...chatsRef.current, newChat];
    setSavedData(null);
    setSelectedChatIdPersisted(newId);
    setWorkflowKey((k) => k + 1);
  };

  // Called by useTripWorkflow when the end destination is confirmed.
  // At that point the chat has a real title and should appear in the TripSearch sidebar.
  const handleChatReady = (chatId, chatTitle) => {
    // Clear the pending ref — this chat is now confirmed and visible in TripSearch
    if (pendingChatRef.current?.id === chatId) {
      pendingChatRef.current = null;
    }
    // Update the title (it was 'New Trip' until now)
    if (chatTitle) {
      setChats((prev) => prev.map((c) => (c.id === chatId ? { ...c, title: chatTitle } : c)));
    }
  };

  const handleDeleteChat = async (chatId) => {
    const remaining = chatsRef.current.filter((c) => c.id !== chatId);
    ChatLogsData.removeChatData(chatId);
    forgetAgentChatId(chatId, agentChatIdMapRef.current);

    // If we're deleting the pending (unconfirmed) chat, clear the ref
    if (pendingChatRef.current?.id === chatId) {
      pendingChatRef.current = null;
    }

    setChats(remaining);
    chatsRef.current = remaining;
    await deleteChat(accessToken, chatId, ChatLogsData);

    if (selectedChatIdRef.current === chatId) {
      // The active chat was deleted — redirect to a new virgin trip
      handleNewChat();
    }
  };

  return (
    <Box className="page-container">
      {searchOpen && (
        <TripSearch
          chats={chats.filter((c) => c.id !== pendingChatRef.current?.id)}
          selectedChatId={selectedChatId}
          isFetchingChats={isFetchingChats}
          getChatInfo={(cid) => {
            const cd = ChatLogsData.getChatDataById(cid);
            const s = deriveProgress(cd);
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
          <Box
            className="fab fab--new"
            onClick={() => {
              if (!isFetchingChats && !loadError) handleNewChat();
            }}
            role="button"
            aria-label="New trip"
          >
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

      {loadError && (
        <Box className="main-content" role="alert">
          <Typography>
            Saved trips could not be loaded. Retry before starting a new trip.
          </Typography>
          <Button onClick={() => window.location.reload()}>Retry loading trips</Button>
        </Box>
      )}
      {/* WorkflowPanel: keyed so bumping workflowKey resets the hook */}
      {!isFetchingChats && !loadError && (
        <WorkflowPanel
          key={workflowKey}
          chatId={selectedChatId}
          agentChatId={getAgentChatId(selectedChatId)}
          setChats={setChats}
          setCurrentStep={setCurrentStep}
          chatsRef={chatsRef}
          accessToken={accessToken}
          ChatLogsData={ChatLogsData}
          activeMessages={activeMessages}
          chatEndRef={chatEndRef}
          savedData={savedData}
          onChatReady={handleChatReady}
        />
      )}
    </Box>
  );
};

export default ChatPage;
