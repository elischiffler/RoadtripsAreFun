import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Data, ChatData, ChatLogs, UserDataContext } from '../states/UserDataContext';

vi.mock('ldrs', () => ({ ring: { register: vi.fn() } }));
vi.mock('../pages/ChatPage/DatabaseUtils', () => ({
  initializeUserData: vi.fn(),
  deleteChat: vi.fn(),
}));
vi.mock('../pages/ChatPage/useTripWorkflow', () => ({
  useTripWorkflow: vi.fn(({ savedData }) => ({
    submit: vi.fn(),
    route: savedData?.route ?? null,
    itinerary: null,
    isLoading: false,
    pendingLocations: savedData?.tripProfile?.pending_locations ?? {},
  })),
  deriveProgress: () => 1,
  renameChatToRoute: vi.fn(),
}));
vi.mock('../pages/ChatPage/TripSearch', () => ({ default: () => null }));
vi.mock('../pages/ChatPage/ChatInput', () => ({ default: () => null }));
vi.mock('../components/buttons/MapButton', () => ({ default: () => null }));
vi.mock('../components/buttons/ItineraryButton', () => ({ default: () => null }));
vi.mock('../components/ThemedTooltip', () => ({ default: ({ children }) => children }));

import ChatPage from '../pages/ChatPage/ChatPage';
import { initializeUserData } from '../pages/ChatPage/DatabaseUtils';
import { useTripWorkflow } from '../pages/ChatPage/useTripWorkflow';

function Harness() {
  const [UserData, setUserData] = useState(new Data());
  const [chats, setChats] = useState([]);
  const [currentStep, setCurrentStep] = useState(1);
  return (
    <UserDataContext.Provider
      value={{ UserData, setUserData, chats, setChats, currentStep, setCurrentStep }}
    >
      <ChatPage />
    </UserDataContext.Provider>
  );
}

describe('ChatPage reload', () => {
  it('renders exact restored candidate labels and sends the explicit selection', async () => {
    sessionStorage.clear();
    sessionStorage.setItem('selectedChatId', '1');
    const partial = new ChatData(1);
    partial.tripProfile = {
      pending_locations: {
        start_address: {
          query: 'SLO',
          candidates: [{ id: 'choice-1', address: 'Salem-Leckrone Airport, Illinois' }],
        },
      },
    };
    initializeUserData.mockResolvedValueOnce({
      chats: [{ id: 1, title: 'Trip', messages: [] }],
      UserData: new Data(new ChatLogs([partial])),
    });
    render(<Harness />);
    const button = await screen.findByRole('button', { name: 'Salem-Leckrone Airport, Illinois' });
    const submit = useTripWorkflow.mock.results.at(-1).value.submit;
    await userEvent.click(button);
    expect(submit).toHaveBeenCalledWith('location_confirmation', {
      field: 'start_address',
      candidateId: 'choice-1',
      address: 'Salem-Leckrone Airport, Illinois',
    });
  });
  it('uses the empty starter chat when a stored selection no longer exists', async () => {
    sessionStorage.clear();
    sessionStorage.setItem('selectedChatId', '9');
    initializeUserData.mockResolvedValueOnce({ chats: [], UserData: new Data() });

    render(<Harness />);
    await waitFor(() =>
      expect(useTripWorkflow).toHaveBeenLastCalledWith(
        expect.objectContaining({ chatId: 1, savedData: null })
      )
    );
    expect(sessionStorage.getItem('selectedChatId')).toBe('1');
  });

  it('restores selected saved chat 1 and its persisted agent ID', async () => {
    sessionStorage.clear();
    sessionStorage.setItem('selectedChatId', '1');
    const chatData = new ChatData(1);
    chatData.endConfirmed = { latitude: 40, longitude: -90, address: 'Destination' };
    chatData.agentChatId = 'saved-agent-id';
    const saved = new Data(new ChatLogs([chatData]));
    initializeUserData.mockResolvedValueOnce({
      chats: [{ id: 1, title: 'Trip', messages: [{ text: 'Hello', sender: 'bot' }] }],
      UserData: saved,
    });

    render(<Harness />);
    await waitFor(() =>
      expect(useTripWorkflow).toHaveBeenLastCalledWith(
        expect.objectContaining({
          chatId: 1,
          agentChatId: 'saved-agent-id',
          savedData: chatData,
        })
      )
    );
    expect(sessionStorage.getItem('selectedChatId')).toBe('1');
  });

  it('keeps a saved partial trip rather than deleting it during reload', async () => {
    sessionStorage.clear();
    sessionStorage.setItem('selectedChatId', '1');
    const partial = new ChatData(1);
    partial.startConfirmed = { latitude: 35, longitude: -120, address: 'Start' };
    const saved = new Data(new ChatLogs([partial]));
    initializeUserData.mockResolvedValueOnce({
      chats: [{ id: 1, title: 'New Trip', messages: [{ text: 'Hi', sender: 'user' }] }],
      UserData: saved,
    });

    render(<Harness />);
    await waitFor(() =>
      expect(useTripWorkflow).toHaveBeenLastCalledWith(
        expect.objectContaining({ chatId: 1, savedData: partial })
      )
    );
  });
});
