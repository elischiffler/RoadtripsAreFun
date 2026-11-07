import { beforeEach, expect, it, vi } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router-dom';
import { renderPage, renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { signOut, safeReturnPath } from '../services/session';
import ShareTripPanel from '../components/ShareTripPanel';
import SharedTripPage from '../pages/SharedTripPage/SharedTripPage';
import SharedTripsPage from '../pages/SharedTripPage/SharedTripsPage';
import * as api from '../services/tripSharing';

vi.mock('../services/tripSharing', async (importOriginal) => ({
  ...(await importOriginal()),
  getSharing: vi.fn(),
  createShareLink: vi.fn(),
  changeSharing: vi.fn(),
  viewShareLink: vi.fn(),
  viewConnectedTrip: vi.fn(),
  listSharedTrips: vi.fn(),
  connectSharedTrip: vi.fn(),
  leaveSharedTrip: vi.fn(),
}));
const token = 's'.repeat(43);
const id = '12345678-1234-4234-8234-123456789abc';
const trip = { chatId: 7, agentChatId: 'original', savedRevision: 'a'.repeat(64) };
const access = {
  share_id: id,
  link_enabled: true,
  link_expires_at: '2030-01-01T00:00:00Z',
  members: [{ id: 'member', display_name: 'Sam', connected_at: '2027-01-01T00:00:00Z' }],
};
const shared = {
  share_id: id,
  title: 'Boulder → Denver',
  route: {
    coordinates: [
      [-105, 40],
      [-104, 41],
    ],
  },
  itinerary: [
    {
      date: '2027-01-01',
      stops: [{ name: 'Museum', time: '10:00', arrival_time: '2027-01-01T10:00:00-07:00' }],
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  localStorage.clear();
  api.clearShareToken();
  fixtureSession('account-a');
  window.history.replaceState(null, '', '/');
  api.getSharing.mockResolvedValue(access);
  api.createShareLink.mockResolvedValue({ ...access, token });
  api.changeSharing.mockResolvedValue({ ...access, link_enabled: false });
  api.viewShareLink.mockResolvedValue(shared);
  api.viewConnectedTrip.mockResolvedValue(shared);
  api.listSharedTrips.mockResolvedValue([shared]);
  api.connectSharedTrip.mockResolvedValue({ share_id: id });
  api.leaveSharedTrip.mockResolvedValue({});
});
const showPanel = async (value = trip) => {
  renderWithProviders(<ShareTripPanel trip={value} />);
  await userEvent.click(screen.getByText('Share this trip'));
  await screen.findByText('Connected accounts');
};
it('explains public capability access and separate member retention before creating/replacing link', async () => {
  await showPanel();
  expect(screen.getByText(/Anyone with the link can view/)).toBeInTheDocument();
  expect(screen.getByText(/Stopping a link keeps these accounts connected/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Replace sharing link' }));
  expect(api.createShareLink).toHaveBeenCalledWith(trip);
  expect(await screen.findByLabelText('Read-only sharing link')).toHaveValue(
    window.location.origin + '/share#token=' + token
  );
  expect(Object.values(sessionStorage).join('')).not.toContain(token);
  expect(Object.values(localStorage).join('')).not.toContain(token);
  await userEvent.click(screen.getByRole('button', { name: 'Stop link' }));
  expect(api.changeSharing).toHaveBeenCalledWith(trip, id, 'link', undefined);
  await screen.findByText('Link stopped. Connected accounts still have access.');
  expect(screen.queryByLabelText('Read-only sharing link')).not.toBeInTheDocument();
});
it('owner removal and Stop all sharing use opaque sharing identity', async () => {
  await showPanel();
  await userEvent.click(
    screen.getByRole('button', { name: 'Remove connection for Sam and stop link' })
  );
  expect(api.changeSharing).toHaveBeenCalledWith(trip, id, 'member', 'member');
  await screen.findByText(
    'Account connection removed and link stopped. Other connected accounts keep access.'
  );
  await userEvent.click(screen.getByRole('button', { name: 'Stop all sharing' }));
  expect(api.changeSharing).toHaveBeenCalledWith(trip, id, 'all', undefined);
});
it('requires a current saved revision and keeps failure recoverable without leaking server detail', async () => {
  await showPanel({ ...trip, savedRevision: null });
  expect(screen.getByRole('button', { name: 'Replace sharing link' })).toBeDisabled();
  expect(api.createShareLink).not.toHaveBeenCalled();
});
it('consumes fragment into ephemeral memory, strips address bar and exposes no owner edit/arrival controls', async () => {
  window.history.replaceState(null, '', '/share#token=' + token);
  renderPage('/share', <SharedTripPage />, '/share#token=' + token);
  await screen.findByText(shared.title);
  expect(api.viewShareLink).toHaveBeenCalledWith(token, expect.any(AbortSignal));
  expect(window.location.hash).toBe('');
  expect(Object.values(sessionStorage).join('')).not.toContain(token);
  expect(Object.values(localStorage).join('')).not.toContain(token);
  expect(
    screen.queryByRole('button', { name: /Mark visited|Undo visited|Arrival|Edit itinerary/ })
  ).not.toBeInTheDocument();
  expect(api.createShareLink).not.toHaveBeenCalled();
  expect(api.changeSharing).not.toHaveBeenCalled();
  await userEvent.type(screen.getByLabelText("Your name for this trip's owner"), 'Traveler');
  await userEvent.click(screen.getByRole('button', { name: 'Connect my account' }));
  expect(api.connectSharedTrip).toHaveBeenCalledWith(token, 'Traveler');
});
it('a sign-in return carries no capability in router state and can reopen from process memory', async () => {
  act(() => signOut());
  function LocationProbe() {
    const location = useLocation();
    return <pre data-testid="return">{JSON.stringify(location.state)}</pre>;
  }
  renderWithProviders(
    <Routes>
      <Route path="/share" element={<SharedTripPage />} />
      <Route path="/login" element={<LocationProbe />} />
    </Routes>,
    { initialPath: '/share#token=' + token }
  );
  await screen.findByText(shared.title);
  await userEvent.click(screen.getByRole('link', { name: 'Sign in to connect this trip' }));
  expect(screen.getByTestId('return')).toHaveTextContent('{"returnTo":"/share"}');
  expect(screen.getByTestId('return').textContent).not.toContain(token);
  expect(api.captureShareToken('')).toBe(token);
  expect(safeReturnPath('/share')).toBe('/share');
  expect(safeReturnPath('/share#token=' + token)).toBe('/plan');
  expect(safeReturnPath('/shared-trips/' + id)).toBe('/shared-trips/' + id);
});
it('refreshes authenticated member view and clears old schedule when revoked', async () => {
  renderPage('/shared-trips/:shareId', <SharedTripPage />, '/shared-trips/' + id);
  await screen.findByText(shared.title);
  expect(api.viewConnectedTrip).toHaveBeenCalledWith(id, expect.any(AbortSignal));
  expect(api.viewShareLink).not.toHaveBeenCalled();
  api.viewConnectedTrip.mockRejectedValueOnce({
    response: { status: 404, data: { detail: 'PRIVATE' } },
  });
  await userEvent.click(screen.getByRole('button', { name: 'Refresh shared trip' }));
  await screen.findByText(/Its owner may have stopped sharing/);
  expect(screen.queryByText('Museum')).not.toBeInTheDocument();
  expect(screen.queryByText('PRIVATE')).not.toBeInTheDocument();
});
it('lists connections separately and ignores an old account response after switching', async () => {
  let resolve;
  api.listSharedTrips.mockReturnValueOnce(
    new Promise((r) => {
      resolve = r;
    })
  );
  api.listSharedTrips.mockResolvedValueOnce([]);
  renderWithProviders(<SharedTripsPage />);
  await waitFor(() => expect(api.listSharedTrips).toHaveBeenCalledTimes(1));
  act(() => fixtureSession('account-b'));
  await screen.findByText(/No connected trips yet/);
  await act(async () => resolve([shared]));
  expect(screen.queryByText(shared.title)).not.toBeInTheDocument();
});
it('fails invalid/missing links locally without sending a guessed capability', async () => {
  renderPage('/share', <SharedTripPage />, '/share#token=not-valid');
  await screen.findByText('Open the complete sharing link from the trip owner.');
  expect(api.viewShareLink).not.toHaveBeenCalled();
});
it('rejects a malformed replacement fragment instead of reusing a previous capability', () => {
  expect(api.captureShareToken('#token=' + token)).toBe(token);
  expect(api.captureShareToken('#token=invalid')).toBeNull();
  expect(api.captureShareToken('')).toBeNull();
});
it('does not falsely claim stale member removal and refreshes to the current connection', async () => {
  await showPanel();
  api.changeSharing.mockRejectedValueOnce({
    response: {
      status: 409,
      data: { detail: 'Connection changed; reload before removing access' },
    },
  });
  await userEvent.click(
    screen.getByRole('button', { name: 'Remove connection for Sam and stop link' })
  );
  await screen.findByText('This trip or its sharing access changed. Reload before continuing.');
  expect(
    screen.queryByText(
      'Account connection removed and link stopped. Other connected accounts keep access.'
    )
  ).not.toBeInTheDocument();
  api.getSharing.mockResolvedValueOnce({
    ...access,
    members: [{ ...access.members[0], id: 'new-member' }],
  });
  await userEvent.click(screen.getByRole('button', { name: 'Refresh sharing access' }));
  await waitFor(() => expect(api.getSharing).toHaveBeenCalledTimes(2));
  await screen.findByRole('button', { name: 'Remove connection for Sam and stop link' });
  await userEvent.click(
    screen.getByRole('button', { name: 'Remove connection for Sam and stop link' })
  );
  expect(api.changeSharing).toHaveBeenLastCalledWith(trip, id, 'member', 'new-member');
});
it('labels the saved plan and renders scheduled rest/sleep times without proof or owner controls', async () => {
  api.viewConnectedTrip.mockResolvedValueOnce({
    ...shared,
    trip_mode: 'one_day',
    itinerary: [
      {
        date: '2027-01-01',
        stops: [
          {
            name: 'Rest time',
            kind: 'rest',
            time: '20:00',
            arrival_time: '2027-01-01T20:00:00-07:00',
            departure_time: '2027-01-01T22:00:00-07:00',
            timezone: 'America/Denver',
          },
          {
            name: 'Sleep time',
            kind: 'sleep',
            time: '22:00',
            arrival_time: '2027-01-01T22:00:00-07:00',
            departure_time: '2027-01-02T07:00:00-07:00',
            timezone: 'America/Denver',
          },
        ],
      },
    ],
  });
  renderPage('/shared-trips/:shareId', <SharedTripPage />, '/shared-trips/' + id);
  await screen.findByText('One-day plan');
  expect(screen.getByText('Rest time')).toBeInTheDocument();
  expect(screen.getByText('Sleep time')).toBeInTheDocument();
  expect(screen.getAllByLabelText(/Jan 1, 2027, 10:00 PM/)).toHaveLength(2);
  expect(screen.getByLabelText(/Jan 2, 2027, 7:00 AM/)).toBeInTheDocument();
  expect(screen.queryByText(/validated|eligibility|proof|guarantee/i)).not.toBeInTheDocument();
  expect(api.createShareLink).not.toHaveBeenCalled();
  expect(api.changeSharing).not.toHaveBeenCalled();
});
