import { beforeEach, expect, it, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { useContext } from 'react';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { Data, ChatData, ChatLogs, UserDataContext } from '../states/UserDataContext';
import { initializeUserData, deleteChat } from '../services/savedTrips';
import SavedTripsPage from '../pages/SavedTripsPage';

vi.mock('../services/savedTrips', () => ({ initializeUserData: vi.fn(), deleteChat: vi.fn() }));

function savedTrips() {
  const first = new ChatData(4);
  first.route = { name: 'Coastal route' };
  first.itinerary = [
    { date: '2027-03-12', stops: [] },
    { date: '2027-03-14', stops: [] },
  ];
  first.startConfirmed = { address: 'Portland, OR' };
  first.endConfirmed = { address: 'Seattle, WA' };
  const second = new ChatData(9);
  return {
    UserData: new Data(new ChatLogs([first, second])),
    chats: [
      { id: 4, title: 'Coastal trip', messages: [{ text: 'Historical message', sender: 'bot' }] },
      { id: 9, title: 'Unfinished trip', messages: [] },
    ],
  };
}
function SelectedTrip() {
  const { UserData } = useContext(UserDataContext);
  return <output>Selected trip: {UserData.chatlogs.currentId}</output>;
}
function renderTrips() {
  return renderWithProviders(
    <Routes>
      <Route path="/trips" element={<SavedTripsPage />} />
      <Route path="/trip" element={<SelectedTrip />} />
      <Route path="/map" element={<SelectedTrip />} />
      <Route path="/itinerary" element={<SelectedTrip />} />
    </Routes>,
    { initialPath: '/trips' }
  );
}
beforeEach(() => {
  sessionStorage.clear();
  fixtureSession();
  vi.resetAllMocks();
});

it.each([
  ['Open trip', '/trip'],
  ['View map', '/map'],
  ['View itinerary', '/itinerary'],
])('opens a saved trip through %s without rendering historical messages', async (label) => {
  const result = savedTrips();
  initializeUserData.mockResolvedValue(result);
  renderTrips();
  await screen.findByText('Coastal trip');
  expect(screen.getByText('Unfinished trip')).toBeInTheDocument();
  expect(screen.queryByText('Historical message')).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getAllByRole('link', { name: label })[0]);
  expect(screen.getByText('Selected trip: 4')).toBeInTheDocument();
  expect(sessionStorage.getItem('selectedChatId')).toBe('4');
  expect(result.chats[0].messages).toHaveLength(1);
});

it('retains a valid saved selection on reload and retries failed reads', async () => {
  sessionStorage.setItem('selectedChatId', '9');
  const result = savedTrips();
  initializeUserData.mockResolvedValueOnce(null).mockResolvedValueOnce(result);
  renderTrips();
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
  await userEvent.setup().click(screen.getByRole('button', { name: 'Retry loading trips' }));
  await screen.findByText('Coastal trip');
  expect(result.UserData.chatlogs.currentId).toBe(9);
});

it('shows the empty state and keeps Studio reachable', async () => {
  initializeUserData.mockResolvedValue({ UserData: new Data(), chats: [] });
  renderTrips();
  expect(await screen.findByText('No saved trips yet.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Plan a trip' })).toHaveAttribute('href', '/plan');
});

it('ignores a late saved-trip response after an account switch', async () => {
  let resolve;
  initializeUserData.mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  renderTrips();
  await act(async () => {
    fixtureSession('other');
    resolve(savedTrips());
  });
  expect(screen.queryByText('Coastal trip')).not.toBeInTheDocument();
});

it('shows endpoints and dates and cancels deletion without making a request', async () => {
  initializeUserData.mockResolvedValue(savedTrips());
  renderTrips();
  expect(await screen.findByText('Portland, OR → Seattle, WA')).toBeInTheDocument();
  expect(screen.getByText('2027-03-12 – 2027-03-14')).toBeInTheDocument();
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Delete Coastal trip' }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(deleteChat).not.toHaveBeenCalled();
  expect(screen.getByText('Coastal trip')).toBeInTheDocument();
});

it('retains the card on failed deletion and removes it only after success', async () => {
  const result = savedTrips();
  initializeUserData.mockResolvedValue(result);
  deleteChat.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  renderTrips();
  await screen.findByText('Coastal trip');
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Delete Coastal trip' }));
  await user.click(screen.getByRole('button', { name: 'Delete trip' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Trip could not be deleted');
  expect(screen.getByText('Coastal trip')).toBeInTheDocument();
  expect(result.UserData.chatlogs.getChatDataById(4)).toBeDefined();
  await user.click(screen.getByRole('button', { name: 'Delete trip' }));
  expect(screen.queryByText('Coastal trip')).not.toBeInTheDocument();
  expect(result.UserData.chatlogs.getChatDataById(4)).toBeUndefined();
  expect(sessionStorage.getItem('selectedChatId')).toBe('9');
});
