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
  it('restores one confirmation per address with one correction hint', async () => {
    sessionStorage.clear();
    const partial = new ChatData(1);
    partial.tripProfile = {
      pending_locations: {
        start_address: {
          query: 'Boulder',
          candidates: [{ id: 'start', address: 'Boulder, Colorado' }],
        },
        destination_address: {
          query: 'Minneapolis',
          candidates: [{ id: 'end', address: 'Minneapolis, Minnesota' }],
        },
      },
    };
    initializeUserData.mockResolvedValueOnce({
      chats: [
        {
          id: 1,
          title: 'Trip',
          messages: [
            {
              sender: 'bot',
              text: 'duplicate fallback',
              presentation: {
                title: 'Updated trip details',
                updated: [],
                notes: [],
                needed: [
                  'Starting location: Confirm the suggested address: Boulder, Colorado.',
                  'Destination: Confirm the suggested address: Minneapolis, Minnesota.',
                ],
              },
            },
          ],
        },
      ],
      UserData: new Data(new ChatLogs([partial])),
    });
    render(<Harness />);
    expect(
      await screen.findByRole('button', { name: 'Confirm starting location' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm destination' })).toBeInTheDocument();
    expect(screen.queryByText('Still needed')).not.toBeInTheDocument();
    expect(screen.queryByText('duplicate fallback')).not.toBeInTheDocument();
    expect(
      screen.getAllByText('Wrong location? Type a different city or address below.')
    ).toHaveLength(1);
    expect(screen.getAllByText(/Boulder, Colorado/)).toHaveLength(1);
    expect(screen.getAllByText(/Minneapolis, Minnesota/)).toHaveLength(1);
  });
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
    const button = await screen.findByRole('button', { name: 'Confirm starting location' });
    expect(button.closest('[role="log"]')).not.toBeNull();
    expect(
      screen.getByText('Suggested address: Salem-Leckrone Airport, Illinois')
    ).toBeInTheDocument();
    const submit = useTripWorkflow.mock.results.at(-1).value.submit;
    await userEvent.click(button);
    expect(submit).toHaveBeenCalledWith('location_confirmation', {
      field: 'start_address',
      candidateId: 'choice-1',
      address: 'Salem-Leckrone Airport, Illinois',
    });
  });
  it('shows only the suggested address and asks for typed corrections', async () => {
    sessionStorage.clear();
    const partial = new ChatData(1);
    partial.tripProfile = {
      pending_locations: {
        destination_address: {
          query: 'Boulder',
          candidates: [
            { id: 'city', address: 'Boulder, Colorado, USA' },
            { id: 'county', address: 'Boulder County, Colorado, USA' },
          ],
        },
      },
    };
    initializeUserData.mockResolvedValueOnce({
      chats: [{ id: 1, title: 'Trip', messages: [] }],
      UserData: new Data(new ChatLogs([partial])),
    });
    render(<Harness />);
    const suggestion = await screen.findByRole('button', { name: 'Confirm destination' });
    expect(suggestion.closest('[role="log"]')).not.toBeNull();
    expect(suggestion).toHaveTextContent('Confirm');
    expect(screen.queryByText('Choose another match')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Boulder County, Colorado, USA' })
    ).not.toBeInTheDocument();
    expect(
      screen.getByText('Wrong location? Type a different city or address below.')
    ).toBeInTheDocument();
    const submit = useTripWorkflow.mock.results.at(-1).value.submit;
    await userEvent.click(suggestion);
    expect(submit).toHaveBeenCalledWith('location_confirmation', {
      field: 'destination_address',
      candidateId: 'city',
      address: 'Boulder, Colorado, USA',
    });
  });
  it('restores lists alongside old plain text messages', async () => {
    sessionStorage.clear();
    initializeUserData.mockResolvedValueOnce({
      chats: [
        {
          id: 1,
          title: 'Trip',
          messages: [
            { sender: 'bot', text: 'Old reply' },
            {
              sender: 'bot',
              text: 'Fallback reply',
              presentation: {
                title: 'Updated trip details',
                updated: ['Hotel budget: $200 per night'],
                needed: [
                  'What time would you like to leave?',
                  'Would you like to provide a car, or skip it?',
                ],
                introduction: 'A few details remain.',
                questions: ['Which evening interests would you like suggestions for (optional)?'],
                notes: [],
              },
            },
          ],
        },
      ],
      UserData: new Data(new ChatLogs([new ChatData(1)])),
    });
    render(<Harness />);
    expect(await screen.findByText('Hotel budget: $200 per night')).toBeInTheDocument();
    expect(screen.getByText('Old reply')).toBeInTheDocument();
    expect(screen.getAllByRole('list')).toHaveLength(3);
    expect(screen.getByText('A few details remain.')).toBeInTheDocument();
    expect(screen.getByText('What time would you like to leave?')).toBeInTheDocument();
    expect(
      screen.getByText('Which evening interests would you like suggestions for (optional)?')
    ).toBeInTheDocument();
    expect(screen.queryByText('Fallback reply')).not.toBeInTheDocument();
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
