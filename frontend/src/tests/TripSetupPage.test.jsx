import { beforeEach, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { getSession, signOut } from '../services/session';
import { Data, ChatData, ChatLogs } from '../states/UserDataContext';
import { newSetupDraft, preferenceWeights } from '../pages/TripSetup/setupModel';
import TripSetupPage from '../pages/TripSetup/TripSetupPage';
import { initializeUserData, ensureChatCreated, updateUserData } from '../services/savedTrips';
import {
  resolveTripLocation,
  planStructuredRoute,
  planStructuredItinerary,
} from '../services/tripPlanner';

vi.mock('../services/savedTrips', () => ({
  initializeUserData: vi.fn(),
  ensureChatCreated: vi.fn(),
  updateUserData: vi.fn(),
}));
vi.mock('../services/tripPlanner', async (original) => ({
  ...(await original()),
  resolveTripLocation: vi.fn(),
  planStructuredRoute: vi.fn(),
  planStructuredItinerary: vi.fn(),
}));
const origin = { address: 'Boulder, Colorado', latitude: 40, longitude: -105 };
const destination = { address: 'Denver, Colorado', latitude: 39.7, longitude: -104.9 };
const route = {
  coordinates: [
    [40, -105],
    [39.7, -104.9],
  ],
  geometry: {
    type: 'LineString',
    coordinates: [
      [-105, 40],
      [-104.9, 39.7],
    ],
  },
  distance: 50000,
  duration: 3600,
  cost: 0,
  start_timezone: 'America/Denver',
  departure_time: '2027-06-01T09:00:00',
  stops: [
    {
      name: 'A real fixture stop',
      visit_duration_seconds: 2700,
      leaving_time: '2027-06-01T10:00:00-06:00',
    },
  ],
};
const draft = {
  ...newSetupDraft(),
  start: 'Boulder',
  destination: 'Denver',
  date: '2027-06-01',
  carStatus: 'skipped',
  interests: ['food'],
};
let existing;
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  fixtureSession();
  sessionStorage.setItem(
    'roadtrips.setup.v1.' + encodeURIComponent(getSession().owner),
    JSON.stringify({ version: 1, draft, step: 4 })
  );
  existing = new ChatData(7);
  existing.route = { name: 'Original saved route' };
  initializeUserData.mockResolvedValue({
    UserData: new Data(new ChatLogs([existing])),
    chats: [{ id: 7, title: 'Existing trip', messages: [{ text: 'Historical', sender: 'bot' }] }],
  });
  resolveTripLocation.mockImplementation(async (query) => [
    query === 'Boulder' ? origin : destination,
  ]);
  planStructuredRoute.mockResolvedValue(route);
  planStructuredItinerary.mockResolvedValue([{ date: 'Tuesday', stops: route.stops }]);
  ensureChatCreated.mockResolvedValue(true);
  updateUserData.mockResolvedValue(true);
});
async function confirm() {
  renderWithProviders(<TripSetupPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Check locations' }));
  await screen.findByRole('heading', { name: 'Confirm your locations' });
  expect(planStructuredRoute).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Confirm locations and plan route' }));
}
it('plans only after explicit provider-address confirmation and creates a new saved trip', async () => {
  await confirm();
  expect(await screen.findByText('Trip saved.')).toBeInTheDocument();
  expect(planStructuredRoute.mock.calls[0].slice(0, 3)).toEqual([draft, origin, destination]);
  expect(ensureChatCreated).toHaveBeenCalledTimes(1);
  const snapshot = ensureChatCreated.mock.calls[0][1];
  expect(snapshot.chatId).toBe(8);
  expect(snapshot.route).toEqual(route);
  expect(snapshot.tripProfile.persona_weights).toEqual(preferenceWeights(draft));
  expect(snapshot.itinerary[0].stops[0].visit_duration_seconds).toBe(2700);
  expect(ensureChatCreated.mock.calls[0][2].find((r) => r.id === 8).messages).toEqual([]);
  expect(existing.route).toEqual({ name: 'Original saved route' });
  expect(sessionStorage.getItem('selectedChatId')).toBe('8');
  expect(screen.getByRole('link', { name: 'View map' })).toHaveAttribute('href', '/map');
  expect(screen.getByRole('link', { name: 'View itinerary' })).toHaveAttribute(
    'href',
    '/itinerary'
  );
  await userEvent.click(screen.getByRole('button', { name: 'Edit draft for another trip' }));
  expect(screen.getByRole('heading', { name: 'Review', exact: true })).toBeInTheDocument();
  expect(existing.route).toEqual({ name: 'Original saved route' });
});
it('retains a partial route and retries only itinerary, updating an existing saved row', async () => {
  planStructuredItinerary.mockRejectedValueOnce(new Error('temporary'));
  await confirm();
  await screen.findByText('Trip saved.');
  expect(screen.queryByRole('link', { name: 'View itinerary' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await screen.findByRole('link', { name: 'View itinerary' });
  expect(planStructuredRoute).toHaveBeenCalledTimes(1);
  expect(updateUserData).toHaveBeenCalledTimes(1);
});
it('does not claim a failed update was saved when retrying persistence', async () => {
  planStructuredItinerary.mockRejectedValueOnce(new Error('temporary'));
  await confirm();
  await screen.findByText('Trip saved.');
  updateUserData.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await screen.findByText('Trip is not saved yet.');
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving trip' }));
  await screen.findByText('Trip saved.');
  expect(updateUserData).toHaveBeenCalledTimes(2);
  expect(ensureChatCreated).toHaveBeenCalledTimes(1);
});
it('preserves results when creating a row fails and retries saving without another provider run', async () => {
  ensureChatCreated.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  await confirm();
  await screen.findByText('Trip is not saved yet.');
  expect(screen.queryByRole('link', { name: 'View map' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving trip' }));
  await screen.findByText('Trip saved.');
  expect(planStructuredRoute).toHaveBeenCalledTimes(1);
});
it('blocks planning when saved IDs could not be loaded and surfaces route validation failures', async () => {
  initializeUserData.mockResolvedValueOnce(null);
  renderWithProviders(<TripSetupPage />);
  await screen.findByRole('button', { name: 'Retry loading trips' });
  expect(screen.queryByRole('button', { name: 'Check locations' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry loading trips' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Check locations' }));
  planStructuredRoute.mockRejectedValueOnce({
    response: { data: { detail: 'Departure must be in the future' } },
  });
  await userEvent.click(
    await screen.findByRole('button', { name: 'Confirm locations and plan route' })
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('Departure must be in the future');
  expect(ensureChatCreated).not.toHaveBeenCalled();
});
it('discards a late planning result after account sign-out', async () => {
  let finish;
  planStructuredRoute.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  await confirm();
  signOut();
  finish(route);
  await waitFor(() => expect(planStructuredRoute).toHaveBeenCalledTimes(1));
  expect(ensureChatCreated).not.toHaveBeenCalled();
});
