import { beforeEach, expect, it, vi } from 'vitest';
import { useContext } from 'react';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { getSession, signOut } from '../services/session';
import { Data, ChatData, ChatLogs, UserDataContext } from '../states/UserDataContext';
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
  expect(planStructuredRoute.mock.calls[0][4].reserveMealSlots).toBe(true);
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
it('keeps a failed itinerary local and retries without saving a partial trip', async () => {
  planStructuredItinerary.mockRejectedValueOnce(new Error('temporary'));
  await confirm();
  await screen.findByText('Trip is not saved yet.');
  expect(ensureChatCreated).not.toHaveBeenCalled();
  expect(updateUserData).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'Retry saving trip' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'View itinerary' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await screen.findByRole('link', { name: 'View itinerary' });
  expect(planStructuredRoute).toHaveBeenCalledTimes(1);
  expect(ensureChatCreated).toHaveBeenCalledTimes(1);
  expect(updateUserData).not.toHaveBeenCalled();
});
it('does not claim a failed creation was saved when retrying persistence', async () => {
  planStructuredItinerary.mockRejectedValueOnce(new Error('temporary'));
  await confirm();
  await screen.findByText('Trip is not saved yet.');
  ensureChatCreated.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await screen.findByText('Trip is not saved yet.');
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving trip' }));
  await screen.findByText('Trip saved.');
  expect(updateUserData).not.toHaveBeenCalled();
  expect(ensureChatCreated).toHaveBeenCalledTimes(2);
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
it('explains meal infeasibility without requesting an itinerary, saving, or completing progress', async () => {
  planStructuredRoute.mockRejectedValueOnce({
    response: {
      status: 422,
      data: {
        detail: 'Lunch cannot fit between the visit and your driving cutoff. Edit your schedule.',
      },
    },
  });
  await confirm();
  expect(await screen.findByRole('alert')).toHaveTextContent('Lunch cannot fit');
  expect(planStructuredItinerary).not.toHaveBeenCalled();
  expect(ensureChatCreated).not.toHaveBeenCalled();
  expect(updateUserData).not.toHaveBeenCalled();
  expect(screen.queryByText('Trip saved.')).not.toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).not.toHaveAttribute(
    'value',
    '100'
  );
  expect(existing.route).toEqual({ name: 'Original saved route' });
});

it('keeps a meal reservation validation failure local until a complete itinerary is available', async () => {
  planStructuredItinerary.mockRejectedValueOnce({
    response: { status: 422, data: { detail: 'Dinner overlaps a visit; revise your schedule.' } },
  });
  await confirm();
  await screen.findByText('Trip is not saved yet.');
  expect(screen.getByRole('alert')).toHaveTextContent('Dinner overlaps a visit');
  expect(ensureChatCreated).not.toHaveBeenCalled();
  expect(updateUserData).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'Retry saving trip' })).not.toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '92'
  );
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

it('saves a fractional nightly target without rounding into the legacy integer slot', async () => {
  const fractional = { ...draft, budget: '150.25' };
  sessionStorage.setItem(
    'roadtrips.setup.v1.' + encodeURIComponent(getSession().owner),
    JSON.stringify({ version: 1, draft: fractional, step: 4 })
  );
  await confirm();
  await screen.findByText('Trip saved.');
  const snapshot = ensureChatCreated.mock.calls[0][1];
  expect(snapshot.hotelBudget).toBeNull();
  expect(snapshot.tripProfile.budget).toBe(150.25);
});

it('waits for explicit selection when a location has several provider matches', async () => {
  resolveTripLocation.mockImplementation(async (query) =>
    query === 'Boulder' ? [origin, { ...origin, address: 'Boulder, Wyoming' }] : [destination]
  );
  renderWithProviders(<TripSetupPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Check locations' }));
  const confirmButton = await screen.findByRole('button', {
    name: 'Confirm locations and plan route',
  });
  expect(confirmButton).toBeDisabled();
  expect(planStructuredRoute).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('radio', { name: 'Boulder, Colorado' }));
  await userEvent.click(confirmButton);
  await screen.findByText('Trip saved.');
  expect(planStructuredRoute.mock.calls[0][1]).toEqual(origin);
  expect(screen.queryByText('Interests sent to the planner')).not.toBeInTheDocument();
});

it('reaches70 with a base route and requests reserved meal time before saving a completed itinerary', async () => {
  let finishRoute, finishItinerary, finishSave;
  planStructuredRoute.mockImplementationOnce(
    (_draft, _origin, _destination, _signal, { onProgress }) => {
      onProgress({ type: 'progress', stage: 'route.initial', state: 'completed' });
      return new Promise((resolve) => {
        finishRoute = resolve;
      });
    }
  );
  planStructuredItinerary.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishItinerary = resolve;
      })
  );
  ensureChatCreated.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishSave = resolve;
      })
  );
  await confirm();
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '70'
  );
  finishRoute(route);
  await waitFor(() => expect(planStructuredItinerary).toHaveBeenCalled());
  expect(planStructuredItinerary.mock.calls[0][2]).toEqual({ includeMealSlots: true });
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '92'
  );
  finishItinerary([{ date: 'Tuesday', stops: route.stops }]);
  await waitFor(() => expect(ensureChatCreated).toHaveBeenCalled());
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '96'
  );
  expect(screen.queryByText('Trip saved.')).not.toBeInTheDocument();
  finishSave(true);
  await screen.findByText('Trip saved.');
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '100'
  );
});

it('discards a stopped itinerary retry before it can publish progress or save', async () => {
  let finishRetry;
  planStructuredItinerary.mockRejectedValueOnce(new Error('temporary')).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishRetry = resolve;
      })
  );
  await confirm();
  await screen.findByText('Trip is not saved yet.');
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await waitFor(() => expect(planStructuredItinerary).toHaveBeenCalledTimes(2));
  const retrySignal = planStructuredItinerary.mock.calls[1][1];
  await userEvent.click(screen.getByRole('button', { name: 'Stop waiting' }));
  expect(retrySignal.aborted).toBe(true);
  await act(async () => finishRetry([{ date: 'Late result', stops: route.stops }]));
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '92'
  );
  expect(screen.queryByRole('link', { name: 'View itinerary' })).not.toBeInTheDocument();
  expect(updateUserData).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Retry itinerary' })).toBeEnabled();
});

it('keeps a newer retry active when a cancelled retry resolves out of order', async () => {
  let finishOld, finishNew;
  planStructuredItinerary
    .mockRejectedValueOnce(new Error('temporary'))
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve;
        })
    )
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishNew = resolve;
        })
    );
  await confirm();
  await screen.findByText('Trip is not saved yet.');
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await userEvent.click(screen.getByRole('button', { name: 'Stop waiting' }));
  await userEvent.click(screen.getByRole('button', { name: 'Retry itinerary' }));
  await waitFor(() => expect(planStructuredItinerary).toHaveBeenCalledTimes(3));
  await act(async () => finishOld([{ date: 'Old retry', stops: route.stops }]));
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '92'
  );
  expect(updateUserData).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Retry itinerary' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Stop waiting' })).toBeEnabled();
  const latest = [{ date: 'New retry', stops: route.stops }];
  await act(async () => finishNew(latest));
  await screen.findByRole('link', { name: 'View itinerary' });
  expect(ensureChatCreated).toHaveBeenCalledTimes(1);
  expect(ensureChatCreated.mock.calls[0][1].itinerary).toEqual(latest);
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '100'
  );
});

it('does not publish saving completion or select a trip after the account signs out', async () => {
  let finishSave;
  ensureChatCreated.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishSave = resolve;
      })
  );
  await confirm();
  await waitFor(() => expect(ensureChatCreated).toHaveBeenCalled());
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '96'
  );
  act(() => signOut());
  await act(async () => finishSave(true));
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '96'
  );
  expect(screen.queryByText('Trip saved.')).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'View itinerary' })).not.toBeInTheDocument();
  expect(sessionStorage.getItem('selectedChatId')).toBeNull();
});

function NavigationProbe() {
  const { UserData, setUserData } = useContext(UserDataContext);
  return (
    <div>
      <p>Selected trip context: {UserData.chatlogs.currentId}</p>
      <button
        onClick={() => {
          const other = new ChatData(99);
          setUserData(new Data(new ChatLogs([other], 99)));
          sessionStorage.setItem('selectedChatId', '99');
        }}
      >
        Open another saved trip
      </button>
    </div>
  );
}
it('does not overwrite another trip selection when an unmounted save finishes', async () => {
  let finishSave;
  ensureChatCreated.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishSave = resolve;
      })
  );
  const view = renderWithProviders(
    <>
      <TripSetupPage key="setup" />
      <NavigationProbe key="navigation" />
    </>
  );
  await userEvent.click(await screen.findByRole('button', { name: 'Check locations' }));
  await userEvent.click(
    await screen.findByRole('button', { name: 'Confirm locations and plan route' })
  );
  await waitFor(() => expect(ensureChatCreated).toHaveBeenCalled());
  view.rerender(<NavigationProbe key="navigation" />);
  await userEvent.click(screen.getByRole('button', { name: 'Open another saved trip' }));
  expect(screen.getByText('Selected trip context: 99')).toBeInTheDocument();
  await act(async () => finishSave(true));
  expect(sessionStorage.getItem('selectedChatId')).toBe('99');
  expect(screen.getByText('Selected trip context: 99')).toBeInTheDocument();
});
