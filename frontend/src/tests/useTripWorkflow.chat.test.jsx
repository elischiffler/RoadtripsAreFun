/**
 * useTripWorkflow — thin agent-chat hook behavior.
 *
 * Verifies the `submit('chat_message', text)` path:
 *   - appends the user's message
 *   - shows + clears the loading bubble
 *   - calls the (mocked) agent helper with the frozen request shape
 *   - renders the bot reply
 *   - falls back to a friendly message when the agent returns null
 *
 * Plus the structured-actions path:
 *   - a `route_updated` action writes the route into the persisted ChatData
 *     snapshot, with startConfirmed/endConfirmed DERIVED from route.coordinates
 *     so Map.jsx doesn't crash
 *   - an `itinerary_updated` action writes the itinerary into the snapshot
 *
 * The agent helper and the DB utils are mocked so no network/DB is touched.
 */
import { useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ── Mock external dependencies of the hook ──────────────────────────────────
vi.mock('../pages/ChatPage/agentChat', () => ({
  sendAgentMessage: vi.fn(),
}));
vi.mock('../pages/ChatPage/DatabaseUtils', () => ({
  updateUserData: vi.fn().mockResolvedValue(null),
}));

import { sendAgentMessage } from '../pages/ChatPage/agentChat';
import { updateUserData } from '../pages/ChatPage/DatabaseUtils';
import { useTripWorkflow } from '../pages/ChatPage/useTripWorkflow';

const CHAT_ID = 5;

// Minimal harness: drives the hook and renders messages live from `chats`.
function Harness({ chatLogsData, onChatReady = () => {}, agentChatId }) {
  const [chats, setChats] = useState([{ id: CHAT_ID, title: 'Trip', messages: [] }]);
  const chatsRef = useRef(chats);
  chatsRef.current = chats;

  const { submit } = useTripWorkflow({
    chatId: CHAT_ID,
    agentChatId,
    setChats,
    setCurrentStep: () => {},
    savedData: null,
    chatsRef,
    accessToken: 'test-token',
    ChatLogsData: chatLogsData ?? { chatdata: [], currentId: CHAT_ID },
    onChatReady,
  });

  const messages = chats.find((c) => c.id === CHAT_ID)?.messages ?? [];

  return (
    <div>
      <button onClick={() => submit('chat_message', 'make it cheaper')}>send</button>
      <ul>
        {messages.map((m, i) => (
          <li key={i} data-sender={m.sender} data-type={m.type}>
            {m.text ?? (m.type === 'loading-chat' ? '[loading]' : '')}
          </li>
        ))}
      </ul>
    </div>
  );
}

Harness.propTypes = {
  chatLogsData: PropTypes.object,
  onChatReady: PropTypes.func,
  agentChatId: PropTypes.string,
};

beforeEach(() => {
  vi.clearAllMocks();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});

describe("submit('chat_message')", () => {
  it('appends the user message, calls the agent, and renders the bot reply', async () => {
    sendAgentMessage.mockResolvedValueOnce({
      reply: 'Sure — I lowered your hotel budget.',
      toolsUsed: [],
      actions: [],
      provider: 'groq',
      usage: null,
    });

    render(<Harness />);
    await userEvent.click(screen.getByText('send'));

    // User message appears immediately
    expect(await screen.findByText('make it cheaper')).toBeInTheDocument();

    // Agent helper called with the frozen request shape
    await waitFor(() => expect(sendAgentMessage).toHaveBeenCalledTimes(1));
    expect(sendAgentMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        accessToken: 'test-token',
        chatId: String(CHAT_ID),
        message: 'make it cheaper',
        clientContext: expect.objectContaining({ hasRoute: false }),
      })
    );

    // Bot reply renders and the loader is gone
    expect(await screen.findByText('Sure — I lowered your hotel budget.')).toBeInTheDocument();
    expect(screen.queryByText('[loading]')).not.toBeInTheDocument();
  });

  it('sends the unique agentChatId as the backend chatId when provided', async () => {
    // B2: the agent conversation key is a globally-unique UUID, NOT the reused
    // integer chat id — so per-chat memory can never collide.
    sendAgentMessage.mockResolvedValueOnce({ reply: 'ok', toolsUsed: [], actions: [] });

    render(<Harness agentChatId="uuid-abc-123" />);
    await userEvent.click(screen.getByText('send'));

    await waitFor(() => expect(sendAgentMessage).toHaveBeenCalledTimes(1));
    expect(sendAgentMessage).toHaveBeenCalledWith(
      expect.objectContaining({ chatId: 'uuid-abc-123' })
    );
  });

  it('shows a generic fallback when the agent returns null', async () => {
    sendAgentMessage.mockResolvedValueOnce(null);

    render(<Harness />);
    await userEvent.click(screen.getByText('send'));

    expect(await screen.findByText('make it cheaper')).toBeInTheDocument();
    await waitFor(() => expect(sendAgentMessage).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/something went wrong on my end/i)).toBeInTheDocument();
  });

  it('shows a transient "try again" fallback on a 503', async () => {
    // sendAgentMessage returns a structured failure carrying the HTTP status.
    sendAgentMessage.mockResolvedValueOnce({ ok: false, status: 503 });

    render(<Harness />);
    await userEvent.click(screen.getByText('send'));

    await waitFor(() => expect(sendAgentMessage).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/trouble reaching my planning service/i)).toBeInTheDocument();
  });
});

describe('applyAgentActions', () => {
  it('writes a route_updated payload into the persisted ChatData snapshot', async () => {
    const routeObj = {
      duration: 3600,
      geometry: { coordinates: [] },
      coordinates: [
        [40.0, -105.0], // start [lat, lon]
        [41.0, -104.0], // a stop
        [42.5, -103.5], // end [lat, lon]
      ],
    };
    sendAgentMessage.mockResolvedValueOnce({
      reply: 'Route ready.',
      toolsUsed: ['generate_route'],
      actions: [
        {
          type: 'route_updated',
          chatId: String(CHAT_ID),
          payload: { route: routeObj, stops: [{}], cost: 250 },
        },
      ],
      provider: 'groq',
      usage: null,
    });

    const chatLogsData = { chatdata: [{ chatId: CHAT_ID }], currentId: CHAT_ID };
    render(<Harness chatLogsData={chatLogsData} />);
    await userEvent.click(screen.getByText('send'));

    await waitFor(() => expect(updateUserData).toHaveBeenCalledTimes(1));

    const snap = updateUserData.mock.calls[0][1];
    // Route written verbatim
    expect(snap.route).toBe(routeObj);
    expect(snap.isComplete).toBe(true);
    expect(snap.budget).toBe(250);
    // startConfirmed / endConfirmed derived from route.coordinates[0] / [-1]
    expect(snap.startConfirmed).toEqual({ latitude: 40.0, longitude: -105.0, address: '' });
    expect(snap.endConfirmed).toEqual({ latitude: 42.5, longitude: -103.5, address: '' });
    // Also mirrored into ChatLogsData so Map/Itinerary read it
    expect(chatLogsData.chatdata[0].route).toBe(routeObj);
  });

  it('writes an itinerary_updated payload into the persisted ChatData snapshot', async () => {
    const itin = [{ date: 'Day 1', stops: [{ name: 'A', address: '1 St', time: '9:00' }] }];
    sendAgentMessage.mockResolvedValueOnce({
      reply: 'Itinerary ready.',
      toolsUsed: ['generate_itinerary'],
      actions: [
        { type: 'itinerary_updated', chatId: String(CHAT_ID), payload: { itinerary: itin } },
      ],
      provider: 'groq',
      usage: null,
    });

    const chatLogsData = { chatdata: [{ chatId: CHAT_ID }], currentId: CHAT_ID };
    render(<Harness chatLogsData={chatLogsData} />);
    await userEvent.click(screen.getByText('send'));

    await waitFor(() => expect(updateUserData).toHaveBeenCalledTimes(1));

    const snap = updateUserData.mock.calls[0][1];
    expect(snap.itinerary).toBe(itin);
    expect(chatLogsData.chatdata[0].itinerary).toBe(itin);
  });

  it('writes a trip_profile_updated payload into the persisted ChatData snapshot', async () => {
    // The agent gathered the start (with coords) into this chat's TripProfile —
    // even before a full route exists, this persists a snapshot (the missing
    // [DB] updateUserData write) and reflects start/stops/budget into the UI.
    sendAgentMessage.mockResolvedValueOnce({
      reply: 'Got it — starting from 482 Luneta Dr.',
      toolsUsed: ['update_trip_profile'],
      actions: [
        {
          type: 'trip_profile_updated',
          chatId: String(CHAT_ID),
          payload: {
            trip_profile: {
              start_address: '482 Luneta Dr, San Luis Obispo, CA',
              start_coords: [35.28, -120.66],
              num_stops: 3,
              budget: 200,
            },
          },
        },
      ],
      provider: 'groq',
      usage: null,
    });

    const chatLogsData = { chatdata: [{ chatId: CHAT_ID }], currentId: CHAT_ID };
    render(<Harness chatLogsData={chatLogsData} />);
    await userEvent.click(screen.getByText('send'));

    await waitFor(() => expect(updateUserData).toHaveBeenCalledTimes(1));

    const snap = updateUserData.mock.calls[0][1];
    // start reflected (address carried through), stops/budget mirrored
    expect(snap.startConfirmed).toEqual({
      latitude: 35.28,
      longitude: -120.66,
      address: '482 Luneta Dr, San Luis Obispo, CA',
    });
    expect(snap.stops).toBe(3);
    expect(snap.budget).toBe(200);
    // No route yet — snapshot is not "complete"
    expect(snap.isComplete).toBe(false);
    // Persisted to ChatLogsData too
    expect(chatLogsData.chatdata[0].stops).toBe(3);
  });
});
