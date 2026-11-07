import { beforeEach, expect, it, vi } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { initializeUserData } from '../services/savedTrips';
import { getSession, requireSignIn } from '../services/session';
import { listSharedTrips } from '../services/tripSharing';
import HomePage from '../pages/HomePage/HomePage';
vi.mock('../services/savedTrips', () => ({ initializeUserData: vi.fn() }));
vi.mock('../services/tripSharing', () => ({ listSharedTrips: vi.fn() }));
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  listSharedTrips.mockResolvedValue([]);
});
const show = () =>
  renderWithProviders(
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/plan" element={<p>Planning entry</p>} />
      <Route path="/shared-trips" element={<p>Connected shared workspace</p>} />
      <Route path="/trips" element={<p>Saved workspace</p>} />
    </Routes>
  );
it('enters planning immediately without a marketing detour or unsigned private read', async () => {
  show();
  await screen.findByText('Planning entry');
  expect(initializeUserData).not.toHaveBeenCalled();
  expect(listSharedTrips).not.toHaveBeenCalled();
});
it.each([{ trips: [] }, { trips: [{ isComplete: true, route: {} }] }])(
  'opens planning or the existing traveler workspace from owner-scoped saved data',
  async ({ trips }) => {
    fixtureSession();
    initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: trips } } });
    show();
    await screen.findByText(trips.length ? 'Saved workspace' : 'Planning entry');
    expect(listSharedTrips).toHaveBeenCalledTimes(trips.length ? 0 : 1);
  }
);

it('returns a retained expired owner to the existing sign-in gate without an unsigned private read', async () => {
  fixtureSession();
  const owner = getSession().owner;
  requireSignIn(getSession());
  expect(getSession().owner).toBe(owner);
  expect(getSession().accessToken).toBeNull();
  show();
  await screen.findByText('Planning entry');
  expect(initializeUserData).not.toHaveBeenCalled();
  expect(listSharedTrips).not.toHaveBeenCalled();
});
it('discards the previous account’s late saved-trip result', async () => {
  fixtureSession('old');
  let finish;
  initializeUserData
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    )
    .mockResolvedValue({ UserData: { chatlogs: { chatdata: [] } } });
  show();
  act(() => fixtureSession('new'));
  await screen.findByText('Planning entry');
  await act(async () => finish({ UserData: { chatlogs: { chatdata: [{ route: {} }] } } }));
  expect(screen.queryByText('Saved workspace')).not.toBeInTheDocument();
});

it('opens a connected shared workspace when no owned route exists', async () => {
  fixtureSession();
  initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: [] } } });
  listSharedTrips.mockResolvedValue([{ share_id: 'fixture-share', title: 'Shared fixture' }]);
  show();
  await screen.findByText('Connected shared workspace');
  expect(listSharedTrips).toHaveBeenCalledTimes(1);
  expect(listSharedTrips.mock.calls[0][0]).toBeInstanceOf(AbortSignal);
  expect(screen.queryByText('Planning entry')).not.toBeInTheDocument();
});
it('offers explicit recovery instead of onboarding when connected-trip lookup is unavailable', async () => {
  fixtureSession();
  initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: [] } } });
  listSharedTrips
    .mockRejectedValueOnce(new Error('private provider detail'))
    .mockResolvedValueOnce([{ share_id: 'fixture-share', title: 'Shared fixture' }]);
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Shared trips could not be checked');
  expect(screen.queryByText('Planning entry')).not.toBeInTheDocument();
  expect(screen.queryByText(/private provider detail/)).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open shared trips' })).toHaveAttribute(
    'href',
    '/shared-trips'
  );
  expect(listSharedTrips).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await screen.findByText('Connected shared workspace');
  expect(listSharedTrips).toHaveBeenCalledTimes(2);
});
it('treats a malformed shared list as unavailable rather than proof of a new account', async () => {
  fixtureSession();
  initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: [] } } });
  listSharedTrips.mockResolvedValue({ unexpected: true });
  show();
  await screen.findByRole('alert');
  expect(screen.queryByText('Planning entry')).not.toBeInTheDocument();
});
it('aborts and ignores a previous account’s late connected-trip list', async () => {
  fixtureSession('old');
  let finish;
  initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: [] } } });
  listSharedTrips
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    )
    .mockResolvedValue([]);
  show();
  await waitFor(() => expect(listSharedTrips).toHaveBeenCalledTimes(1));
  const oldSignal = listSharedTrips.mock.calls[0][0];
  act(() => fixtureSession('new'));
  expect(oldSignal.aborted).toBe(true);
  await screen.findByText('Planning entry');
  await act(async () => finish([{ share_id: 'old-private-share', title: 'Old account trip' }]));
  expect(screen.queryByText('Connected shared workspace')).not.toBeInTheDocument();
  expect(screen.queryByText('Old account trip')).not.toBeInTheDocument();
});
it('aborts the connected-trip lookup on navigation away', async () => {
  fixtureSession();
  initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: [] } } });
  listSharedTrips.mockImplementation(() => new Promise(() => {}));
  const view = show();
  await waitFor(() => expect(listSharedTrips).toHaveBeenCalledTimes(1));
  const signal = listSharedTrips.mock.calls[0][0];
  view.unmount();
  expect(signal.aborted).toBe(true);
});
