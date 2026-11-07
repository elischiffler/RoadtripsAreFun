import { useContext } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import { UserDataContext, UserDataProvider } from '../states/UserDataContext';
import ItineraryPage from '../pages/ItineraryPage/ItineraryPage';
import { fixtureSession } from './sessionFixtures';
vi.mock('axios');

const history = {
  id: 42,
  title: 'Saved coast trip',
  messages: [
    { text: 'Please include a forest walk.', sender: 'user' },
    { text: 'Your coastal route is ready.', sender: 'bot' },
  ],
};
const trip = {
  chatId: 42,
  savedRevision: 'a'.repeat(64),
  itinerary: [
    { date: 'Day 1', stops: [{ name: 'Saved forest walk', provider_id: 'park:1', time: '8 AM' }] },
  ],
  presentation: { futureField: 'preserve' },
};
function ContextSnapshot() {
  const { chats, UserData } = useContext(UserDataContext);
  return (
    <output data-testid="restored-context">
      {JSON.stringify({ chats, ids: UserData.chatlogs.chatdata.map((item) => item.chatId) })}
    </output>
  );
}
function ReloadFixture() {
  return (
    <MemoryRouter initialEntries={['/itinerary']}>
      <UserDataProvider>
        <ItineraryPage />
        <ContextSnapshot />
      </UserDataProvider>
    </MemoryRouter>
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  fixtureSession();
  sessionStorage.setItem('selectedChatId', '42');
});
it('restores selected trip and historical chat together, then persists mark and undo through the real saved-trip service', async () => {
  axios.get.mockResolvedValueOnce({
    data: [
      [{ chatId: 7 }, { id: 7, messages: [] }],
      [trip, history],
    ],
  });
  axios.put.mockResolvedValue({ status: 200, data: { savedRevision: 'a'.repeat(64) } });
  render(<ReloadFixture />);
  await userEvent.click(
    await screen.findByRole('button', { name: 'Mark visited: Saved forest walk' })
  );
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(axios.put).toHaveBeenCalledTimes(1);
  expect(axios.put.mock.calls[0][0]).toMatch(/chats\/update\/42$/);
  const marked = axios.put.mock.calls[0][1];
  expect(marked.ChatLog).toEqual(history);
  expect(marked.ExpectedRevision).toBe('a'.repeat(64));
  expect(marked.UpdateScope).toBe('presentation');
  expect(marked.ChatData.presentation.visitedStopIds).toHaveLength(1);
  expect(marked.ChatData.presentation.futureField).toBe('preserve');
  expect(axios.post).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Undo visited: Saved forest walk' }));
  await waitFor(() => expect(axios.put).toHaveBeenCalledTimes(2));
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(axios.put.mock.calls[1][1].ChatData.presentation.visitedStopIds).toEqual([]);
  expect(axios.put.mock.calls[1][1].ChatLog).toEqual(history);
  expect(JSON.parse(screen.getByTestId('restored-context').textContent).chats).toEqual([
    { id: 7, messages: [] },
    history,
  ]);
});
it('does not hydrate either the trip or historical chat after an account changes during reload', async () => {
  let finish;
  axios.get
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    )
    .mockResolvedValue({ data: [] });
  render(<ReloadFixture />);
  await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(1));
  act(() => fixtureSession('different-owner'));
  await act(async () => {
    finish({ data: [[trip, history]] });
  });
  await waitFor(() =>
    expect(JSON.parse(screen.getByTestId('restored-context').textContent)).toEqual({
      chats: [],
      ids: [],
    })
  );
  expect(screen.queryByText('Saved forest walk')).not.toBeInTheDocument();
  expect(axios.put).not.toHaveBeenCalled();
});
