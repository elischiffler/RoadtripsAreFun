import { loadRouteAlternatives } from '../services/routeAlternatives';
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
import { loadPreferenceProfiles, saveNewTripPreferences } from '../services/preferenceProfiles';
import { initializeUserData, ensureChatCreated, updateUserData } from '../services/savedTrips';
import {
  resolveTripLocation,
  estimateStructuredRoute,
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
  estimateStructuredRoute: vi.fn(),
  planStructuredItinerary: vi.fn(),
}));
vi.mock('../services/preferenceProfiles', async (original) => ({
  ...(await original()),
  loadPreferenceProfiles: vi.fn(async () => []),
  saveNewTripPreferences: vi.fn(async () => undefined),
}));
import {
  assessPlanningCandidate,
  buildCandidatePayload,
  cancelCandidateRequest,
  confirmPlanningCandidate,
  registerCandidateRequest,
} from '../services/planningCandidates';
vi.mock('../services/planningCandidates', () => ({
  assessPlanningCandidate: vi.fn(),
  buildCandidatePayload: vi.fn(),
  cancelCandidateRequest: vi.fn(async () => {}),
  confirmPlanningCandidate: vi.fn(),
  registerCandidateRequest: vi.fn(),
}));
vi.mock('../services/routeAlternatives', () => ({
  loadRouteAlternatives: vi.fn(async () => ({ places: [] })),
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
  loadPreferenceProfiles.mockResolvedValue([]);
  loadRouteAlternatives.mockResolvedValue({ places: [] });
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
  estimateStructuredRoute.mockResolvedValue(route);
  cancelCandidateRequest.mockResolvedValue(undefined);
  registerCandidateRequest.mockResolvedValue({});
  buildCandidatePayload.mockResolvedValue({ immutable: true });
  assessPlanningCandidate.mockResolvedValue({
    candidate_id: 'fixture-candidate',
    input_key: 'f'.repeat(64),
    expires_at: '2099-01-01T00:00:00Z',
    one_day: { eligible: true, elapsed_seconds: 7200, threshold_seconds: 43200 },
    candidate_route: route,
  });
  confirmPlanningCandidate.mockResolvedValue(route);
  planStructuredItinerary.mockResolvedValue([{ date: 'Tuesday', stops: route.stops }]);
  ensureChatCreated.mockResolvedValue(true);
  updateUserData.mockResolvedValue(true);
});
async function confirm(finish = true) {
  renderWithProviders(<TripSetupPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Check trip options' }));
  expect(confirmPlanningCandidate).not.toHaveBeenCalled();
  if (finish)
    await userEvent.click(await screen.findByRole('button', { name: 'Finish in one day' }));
}
it('plans only after explicit provider-address confirmation and creates a new saved trip', async () => {
  await confirm();
  expect(await screen.findByText('Trip saved.')).toBeInTheDocument();
  expect(confirmPlanningCandidate.mock.calls[0][1]).toBe('one_day');
  expect(confirmPlanningCandidate.mock.calls[0][2]).toEqual(draft);
  expect(ensureChatCreated).toHaveBeenCalledTimes(1);
  const snapshot = ensureChatCreated.mock.calls[0][1];
  expect(snapshot.chatId).toBe(8);
  expect(snapshot.route).toEqual(route);
  expect(snapshot.tripProfile.persona_weights).toEqual(preferenceWeights(draft));
  expect(snapshot.itinerary[0].stops[0].visit_duration_seconds).toBe(2700);
  expect(ensureChatCreated.mock.calls[0][2].find((r) => r.id === 8).messages).toEqual([]);
  expect(existing.route).toEqual({ name: 'Original saved route' });
  expect(sessionStorage.getItem('selectedChatId')).toBe('8');
  expect(screen.getByRole('link', { name: 'Open trip' })).toHaveAttribute('href', '/trip');
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
  expect(confirmPlanningCandidate).toHaveBeenCalledTimes(1);
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
  expect(screen.queryByRole('link', { name: 'Open trip' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving trip' }));
  await screen.findByText('Trip saved.');
  expect(confirmPlanningCandidate).toHaveBeenCalledTimes(1);
});
it('blocks planning when saved IDs could not be loaded and surfaces route validation failures', async () => {
  initializeUserData.mockResolvedValueOnce(null);
  renderWithProviders(<TripSetupPage />);
  await screen.findByRole('button', { name: 'Retry loading trips' });
  expect(screen.queryByRole('button', { name: 'Check trip options' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry loading trips' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Check trip options' }));
  confirmPlanningCandidate.mockRejectedValueOnce({
    response: { data: { detail: 'Departure must be in the future' } },
  });
  await userEvent.click(await screen.findByRole('button', { name: 'Finish in one day' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Departure must be in the future');
  expect(ensureChatCreated).not.toHaveBeenCalled();
});
it('explains meal infeasibility without requesting an itinerary, saving, or completing progress', async () => {
  confirmPlanningCandidate.mockRejectedValueOnce({
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
  confirmPlanningCandidate.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  await confirm();
  signOut();
  finish(route);
  await waitFor(() => expect(confirmPlanningCandidate).toHaveBeenCalledTimes(1));
  expect(ensureChatCreated).not.toHaveBeenCalled();
});

it('shows departure guidance without saving a trip or falsely completing planning', async () => {
  assessPlanningCandidate.mockImplementationOnce(
    (_draft, _route, _requestId, _signal, onProgress) => {
      onProgress({ type: 'progress', stage: 'route.initial', state: 'completed' });
      return Promise.reject({
        response: {
          status: 422,
          data: { detail: 'Choose a departure date and time in the future.' },
        },
      });
    }
  );
  await confirm(false);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Choose a departure date and time in the future.'
  );
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '70'
  );
  expect(ensureChatCreated).not.toHaveBeenCalled();
  expect(updateUserData).not.toHaveBeenCalled();
  expect(planStructuredItinerary).not.toHaveBeenCalled();
  expect(screen.queryByText('Trip saved.')).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'View itinerary' })).not.toBeInTheDocument();
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
  expect(snapshot.tripProfile.budget).toBeNull(); // one-day carries no lodging target
});

it('requires explicit ambiguous endpoint selection before leaving the route step', async () => {
  resolveTripLocation.mockImplementation(async (query) =>
    query === 'Boulder' ? [origin, { ...origin, address: 'Boulder, Wyoming' }] : [destination]
  );
  renderWithProviders(<TripSetupPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Check trip options' }));
  const useLocations = await screen.findByRole('button', {
    name: 'Use these locations for estimate',
  });
  expect(useLocations).toBeDisabled();
  expect(assessPlanningCandidate).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('radio', { name: 'Boulder, Colorado' }));
  await userEvent.click(useLocations);
  await screen.findByText(/About 1.0 hours driving/);
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(await screen.findByRole('heading', { name: 'People' })).toBeInTheDocument();
  expect(assessPlanningCandidate).not.toHaveBeenCalled();
});

it('reaches70 with a base route and requests reserved meal time before saving a completed itinerary', async () => {
  let finishRoute, finishItinerary, finishSave;
  assessPlanningCandidate.mockImplementationOnce(
    (_draft, _route, _requestId, _signal, onProgress) => {
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
  await confirm(false);
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '70'
  );
  finishRoute({
    candidate_id: 'fixture-candidate',
    input_key: 'f'.repeat(64),
    expires_at: '2099-01-01',
    one_day: { eligible: true, elapsed_seconds: 7200, threshold_seconds: 43200 },
    candidate_route: route,
  });
  await userEvent.click(await screen.findByRole('button', { name: 'Finish in one day' }));
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
  expect(
    screen.queryByRole('progressbar', { name: 'Trip planning milestones' })
  ).not.toBeInTheDocument();
  expect(screen.queryByText('Trip saved.')).not.toBeInTheDocument();
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
  await userEvent.click(await screen.findByRole('button', { name: 'Check trip options' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Finish in one day' }));
  await waitFor(() => expect(ensureChatCreated).toHaveBeenCalled());
  view.rerender(<NavigationProbe key="navigation" />);
  await userEvent.click(screen.getByRole('button', { name: 'Open another saved trip' }));
  expect(screen.getByText('Selected trip context: 99')).toBeInTheDocument();
  await act(async () => finishSave(true));
  expect(sessionStorage.getItem('selectedChatId')).toBe('99');
  expect(screen.getByText('Selected trip context: 99')).toBeInTheDocument();
});

it('keeps the trip saved when profile saving fails and retries only the profile with the same id', async () => {
  saveNewTripPreferences
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce(undefined);
  await confirm();
  await screen.findByText('Trip saved.');
  expect(
    screen.getByText('Trip saved. Preferences could not be saved; retry below.')
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving preferences' }));
  await screen.findByText('Preferences saved for future trips.');
  expect(saveNewTripPreferences).toHaveBeenCalledTimes(2);
  expect(saveNewTripPreferences.mock.calls[0]).toEqual(saveNewTripPreferences.mock.calls[1]);
  expect(ensureChatCreated).toHaveBeenCalledTimes(1);
  expect(updateUserData).not.toHaveBeenCalled();
  expect(confirmPlanningCandidate).toHaveBeenCalledTimes(1);
  expect(planStructuredItinerary).toHaveBeenCalledTimes(1);
});

it('requires reloading a newer saved trip after a late create retry conflict without offering another blind retry', async () => {
  ensureChatCreated.mockImplementationOnce(async (_token, snapshot) => {
    snapshot.saveConflict = true;
    return false;
  });
  await confirm();
  expect(await screen.findByText('Saved trip changed; reload required.')).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('Open Saved trips to reload');
  expect(screen.queryByRole('button', { name: 'Retry saving trip' })).not.toBeInTheDocument();
  expect(screen.queryByText('Trip saved.')).not.toBeInTheDocument();
});

it('waits for explicit assessment and presents no hotel questions or completion from a preview', async () => {
  let finish;
  assessPlanningCandidate.mockImplementationOnce((_draft, _route, _id, _signal, progress) => {
    progress({
      type: 'progress',
      stage: 'route.preview',
      state: 'completed',
      phase: 'checking',
      preview_only: true,
      geometry: route.geometry,
      stops: [],
    });
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  await confirm(false);
  expect(registerCandidateRequest).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('button', { name: 'Finish in one day' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Hotel target per room / night')).not.toBeInTheDocument();
  expect(ensureChatCreated).not.toHaveBeenCalled();
  expect(screen.getByRole('progressbar', { name: 'Trip planning milestones' })).toHaveAttribute(
    'value',
    '70'
  );
  await act(async () =>
    finish({ one_day: { eligible: false, elapsed_seconds: 50000 }, candidate_route: route })
  );
  expect(screen.queryByRole('button', { name: 'Finish in one day' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Allow overnight stays' })).toBeEnabled();
});
it('retains the exact registered request and immutable input body on an explicit uncertain retry', async () => {
  assessPlanningCandidate.mockRejectedValueOnce(new Error('connection lost'));
  await confirm(false);
  await screen.findByRole('alert');
  expect(assessPlanningCandidate).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: 'Retry trip option check' }));
  await screen.findByRole('button', { name: 'Finish in one day' });
  expect(registerCandidateRequest).toHaveBeenCalledTimes(1);
  expect(buildCandidatePayload).toHaveBeenCalledTimes(1);
  expect(assessPlanningCandidate.mock.calls[1][2]).toBe(assessPlanningCandidate.mock.calls[0][2]);
  expect(assessPlanningCandidate.mock.calls[1][5]).toBe(assessPlanningCandidate.mock.calls[0][5]);
  expect(ensureChatCreated).not.toHaveBeenCalled();
});
it('requires a fresh explicit check after410 without automatic re-registration or AI replay', async () => {
  assessPlanningCandidate.mockRejectedValueOnce({
    response: {
      status: 410,
      data: {
        code: 'candidate_expired',
        detail: 'These trip options expired. Check again explicitly.',
      },
    },
  });
  await confirm(false);
  await screen.findByRole('alert');
  expect(registerCandidateRequest).toHaveBeenCalledTimes(1);
  expect(assessPlanningCandidate).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole('button', { name: 'Check trip options' }));
  await screen.findByRole('button', { name: 'Finish in one day' });
  expect(registerCandidateRequest).toHaveBeenCalledTimes(2);
  expect(assessPlanningCandidate.mock.calls[1][2]).not.toBe(
    assessPlanningCandidate.mock.calls[0][2]
  );
});
it('collects hotel occupancy only for stays allowed and accepts a flexible route with no hotel', async () => {
  assessPlanningCandidate.mockResolvedValueOnce({
    candidate_id: 'fixture-candidate',
    input_key: 'f'.repeat(64),
    expires_at: '2099-01-01',
    one_day: { eligible: false, elapsed_seconds: null },
    candidate_route: null,
  });
  await confirm(false);
  await userEvent.click(await screen.findByRole('button', { name: 'Allow overnight stays' }));
  expect(screen.getByLabelText('Hotel target per room / night')).toHaveValue(150);
  await userEvent.click(screen.getByRole('button', { name: 'Add a room' }));
  await userEvent.click(screen.getByRole('button', { name: 'Plan with stays allowed' }));
  expect(screen.getByText('Room occupants must add up to the total people.')).toBeInTheDocument();
  expect(confirmPlanningCandidate).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Remove room 2' }));
  await userEvent.click(screen.getByRole('button', { name: 'Plan with stays allowed' }));
  await screen.findByText('Trip saved.');
  expect(confirmPlanningCandidate.mock.calls[0][1]).toBe('overnight');
  expect(ensureChatCreated.mock.calls[0][1].tripProfile.hotel_rooms).toEqual([
    { adults: 1, child_ages: [] },
  ]);
  expect(screen.queryByText(/hotel is guaranteed/i)).not.toBeInTheDocument();
});

it('keeps hotel typing focus while editing deferred stay answers', async () => {
  await confirm(false);
  await userEvent.click(await screen.findByRole('button', { name: 'Allow overnight stays' }));
  const budget = screen.getByLabelText('Hotel target per room / night');
  await userEvent.clear(budget);
  await userEvent.type(budget, '125.50');
  expect(budget).toHaveFocus();
  expect(budget).toHaveValue(125.5);
  expect(assessPlanningCandidate).toHaveBeenCalledTimes(1);
  expect(confirmPlanningCandidate).not.toHaveBeenCalled();
});

it('starts a new explicit generation after a definitive typed terminal503 while never auto-replaying', async () => {
  assessPlanningCandidate.mockRejectedValueOnce({
    code: 'candidate_unavailable',
    response: {
      status: 503,
      data: {
        code: 'candidate_unavailable',
        detail:
          'Trip options could not be verified. Your draft is kept. Check again explicitly when ready.',
      },
    },
  });
  await confirm(false);
  await screen.findByRole('alert');
  expect(registerCandidateRequest).toHaveBeenCalledTimes(1);
  expect(assessPlanningCandidate).toHaveBeenCalledTimes(1);
  const failedId = assessPlanningCandidate.mock.calls[0][2];
  await userEvent.click(screen.getByRole('button', { name: 'Check trip options' }));
  await screen.findByRole('button', { name: 'Finish in one day' });
  expect(registerCandidateRequest).toHaveBeenCalledTimes(2);
  expect(assessPlanningCandidate.mock.calls[1][2]).not.toBe(failedId);
  expect(ensureChatCreated).not.toHaveBeenCalled();
});
