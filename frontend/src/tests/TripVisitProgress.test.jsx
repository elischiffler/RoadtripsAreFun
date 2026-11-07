import { useContext, useState } from 'react';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Data, ChatData, ChatLogs, UserDataContext } from '../states/UserDataContext';
import ItineraryPage from '../pages/ItineraryPage/ItineraryPage';
import { updateUserData } from '../services/savedTrips';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
vi.mock('../services/savedTrips', async (original) => ({
  ...(await original()),
  updateUserData: vi.fn(),
}));
const makeTrip = () => {
  const trip = new ChatData(42);
  trip.itinerary = [
    {
      date: 'Day 1',
      stops: [
        { name: 'Past visit', provider_id: 'park:1', time: '8 AM' },
        {
          id: 'meal:day:lunch',
          kind: 'meal',
          name: 'Lunch',
          window_start: '2030-11-03T12:00:00-08:00',
          window_end: '2030-11-03T14:00:00-08:00',
          timezone: 'America/Los_Angeles',
          optional: true,
          time: 'Unscheduled',
        },
      ],
    },
  ];
  trip.presentation = { futureField: 'keep' };
  return trip;
};
function CurrentData() {
  const { UserData } = useContext(UserDataContext);
  return (
    <output data-testid="presentation">
      {JSON.stringify(UserData.chatlogs.chatdata[0].presentation)}
    </output>
  );
}
function Fixture() {
  const [UserData, setUserData] = useState(() => new Data(new ChatLogs([makeTrip()], 42)));
  return (
    <MemoryRouter>
      <UserDataContext.Provider
        value={{ UserData, setUserData, chats: [{ id: 42, messages: [] }] }}
      >
        <ItineraryPage />
        <CurrentData />
      </UserDataContext.Provider>
    </MemoryRouter>
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  fixtureSession();
});
it('marks only explicit visits, preserves unknown data, saves and supports undo', async () => {
  updateUserData.mockResolvedValue(true);
  render(<Fixture />);
  expect(screen.getByText('0 of 1 stops visited')).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Open meal windows' })).toHaveTextContent('12:00 PM');
  expect(screen.queryByRole('button', { name: /visited: Lunch/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Mark visited: Past visit' }));
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(screen.getByText('1 of 1 stops visited')).toBeInTheDocument();
  expect(updateUserData.mock.calls[0][1].presentation.futureField).toBe('keep');
  await userEvent.click(screen.getByRole('button', { name: 'Undo visited: Past visit' }));
  expect(screen.getByText('0 of 1 stops visited')).toBeInTheDocument();
  expect(updateUserData.mock.calls[1][1].presentation.visitedStopIds).toEqual([]);
});
it('keeps failed updates local with retry and does not claim they were saved', async () => {
  updateUserData.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<Fixture />);
  await userEvent.click(screen.getByRole('button', { name: 'Mark visited: Past visit' }));
  expect(await screen.findByText(/could not be saved/)).toBeInTheDocument();
  expect(screen.getByText('1 of 1 stops visited')).toBeInTheDocument();
  expect(screen.queryByText('Visit updates saved.')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving visits' }));
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(updateUserData.mock.calls[1][1].presentation).toEqual(
    updateUserData.mock.calls[0][1].presentation
  );
});
it('ignores a completion after the account session changes', async () => {
  let finish;
  updateUserData.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  render(<Fixture />);
  await userEvent.click(screen.getByRole('button', { name: 'Mark visited: Past visit' }));
  expect(screen.getByRole('button', { name: 'Undo visited: Past visit' })).toBeDisabled();
  act(() => signOut());
  await act(async () => finish(true));
  expect(screen.queryByText('Visit updates saved.')).not.toBeInTheDocument();
});
it('switches saved trip views without losing the selected trip identity', async () => {
  render(<Fixture />);
  await userEvent.click(screen.getByRole('link', { name: 'View map' }));
  expect(sessionStorage.getItem('selectedChatId')).toBe('42');
});
