import { beforeEach, expect, it, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { initializeUserData } from '../services/savedTrips';
import { getSession, requireSignIn } from '../services/session';
import HomePage from '../pages/HomePage/HomePage';
vi.mock('../services/savedTrips', () => ({ initializeUserData: vi.fn() }));
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
});
const show = () =>
  renderWithProviders(
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/plan" element={<p>Planning entry</p>} />
      <Route path="/trips" element={<p>Saved workspace</p>} />
    </Routes>
  );
it('enters planning immediately without a marketing detour or unsigned private read', async () => {
  show();
  await screen.findByText('Planning entry');
  expect(initializeUserData).not.toHaveBeenCalled();
});
it.each([{ trips: [] }, { trips: [{ isComplete: true, route: {} }] }])(
  'opens planning or the existing traveler workspace from owner-scoped saved data',
  async ({ trips }) => {
    fixtureSession();
    initializeUserData.mockResolvedValue({ UserData: { chatlogs: { chatdata: trips } } });
    show();
    await screen.findByText(trips.length ? 'Saved workspace' : 'Planning entry');
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
