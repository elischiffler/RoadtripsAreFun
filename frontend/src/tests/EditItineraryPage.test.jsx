/**
 * Edit itinerary — mocked route browsing without provider or persistence calls.
 * mapbox-gl and Map component are both stubbed.
 */
import { useState } from 'react';
import { it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { previewTripEdit, persistTripEdit } from '../services/tripEdits';
import { loadRouteAlternatives } from '../services/routeAlternatives';
import PropTypes from 'prop-types';
import { render } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import {
  UserDataContext,
  UserDataProvider,
  Data,
  ChatLogs,
  ChatData,
} from '../states/UserDataContext';
import customTheme from '../components/Theme';
import EditItineraryPage from '../pages/EditItineraryPage/EditItineraryPage';

vi.mock('../services/tripEdits', async (original) => ({
  ...(await original()),
  previewTripEdit: vi.fn(),
  persistTripEdit: vi.fn(),
}));

vi.mock('../services/routeAlternatives', () => ({ loadRouteAlternatives: vi.fn() }));

// Stub the Map component — it needs real Mapbox tokens and a DOM canvas
vi.mock('../components/Map', () => ({
  default: () => <div data-testid="map-stub">Map Stub</div>,
}));

// Inject saved trip context.
function renderEditorWithData(UserData) {
  function Wrapper({ children }) {
    const [current, setCurrent] = useState(UserData);
    return (
      <UserDataProvider>
        <ThemeProvider theme={customTheme}>
          <MemoryRouter initialEntries={['/itinerary/edit']}>
            <UserDataContext.Provider
              value={{
                UserData: current,
                setUserData: setCurrent,
                chats: [],
                setChats: vi.fn(),
                currentStep: 1,
                setCurrentStep: vi.fn(),
              }}
            >
              {children}
            </UserDataContext.Provider>
          </MemoryRouter>
        </ThemeProvider>
      </UserDataProvider>
    );
  }

  Wrapper.propTypes = { children: PropTypes.node.isRequired };
  return render(<EditItineraryPage />, { wrapper: Wrapper });
}

// Helper — build a UserData with a route on the current chat
function buildUserDataWithRoute(route = null) {
  const cd = new ChatData(1);
  cd.route = route;
  const logs = new ChatLogs([cd], 1);
  return new Data(logs);
}

beforeEach(() => vi.clearAllMocks());

it('loads source-labelled nearby ideas from this route without changing the route', async () => {
  const route = {
    stops: [],
    geometry: {
      coordinates: [
        [-120, 37],
        [-121, 38],
      ],
    },
  };
  loadRouteAlternatives.mockResolvedValueOnce({
    places: [
      {
        id: 'catalog:1',
        name: 'Forest',
        coordinates: [37, -120],
        source_attribution: 'Fixture catalog',
        offset_miles: 2.34,
        detour_minutes: null,
        url: 'https://example.test/forest',
      },
    ],
    notice: 'Check detour timing',
    coverage: { continuous: false },
  });
  renderEditorWithData(buildUserDataWithRoute(route));
  await userEvent.click(screen.getByRole('button', { name: 'Find places' }));
  expect(await screen.findByText('Forest')).toBeInTheDocument();
  expect(loadRouteAlternatives).toHaveBeenCalledWith(route, expect.any(AbortSignal));
  expect(screen.getByText('Source: Fixture catalog')).toBeInTheDocument();
  expect(screen.getByText(/Choose a place, recalculate/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'View on map: Forest' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Place information: Forest' })).toHaveAttribute(
    'href',
    'https://example.test/forest'
  );
  expect(screen.getByText(/2.3 miles from route sample/)).toHaveTextContent(
    'driving detour unverified'
  );
  expect(screen.getByText(/gaps between searches/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'View on map: Forest' }));
  expect(screen.getByLabelText('Trip route map')).toHaveFocus();
  expect(route.stops).toEqual([]);
});
it('shows an error and retries failed nearby lookup', async () => {
  loadRouteAlternatives
    .mockRejectedValueOnce(new Error('unavailable'))
    .mockResolvedValueOnce({ places: [], notice: '' });
  renderEditorWithData(buildUserDataWithRoute({ stops: [] }));
  await userEvent.click(screen.getByRole('button', { name: 'Find places' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
  await userEvent.click(screen.getByRole('button', { name: 'Retry search' }));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('No places found'));
});

it('aborts pending route browsing when the editor unmounts', async () => {
  loadRouteAlternatives.mockImplementation(() => new Promise(() => {}));
  const view = renderEditorWithData(buildUserDataWithRoute({ stops: [] }));
  await userEvent.click(screen.getByRole('button', { name: 'Find places' }));
  const signal = loadRouteAlternatives.mock.calls[0][1];
  expect(signal.aborted).toBe(false);
  view.unmount();
  expect(signal.aborted).toBe(true);
});

it('discards recalculated preview without changing context or dispatching a save', async () => {
  const trip = buildUserDataWithRoute({
    duration: 3600,
    distance: 1609,
    stops: [
      { name: 'Old stop', type: 'stop' },
      { name: 'End', type: 'end' },
    ],
  });
  const initial = trip.chatlogs.chatdata[0];
  loadRouteAlternatives.mockResolvedValue({
    places: [{ id: 'catalog:1', name: 'New place', coordinates: [37, -120] }],
  });
  previewTripEdit.mockResolvedValue({
    route: { duration: 7200, distance: 3218, stops: [{ name: 'New place', type: 'stop' }] },
    itinerary: [],
  });
  renderEditorWithData(trip);
  await userEvent.click(screen.getByRole('button', { name: 'Find places' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Choose New place' }));
  await userEvent.click(screen.getByRole('button', { name: 'Recalculate trip' }));
  expect(await screen.findByText('Review changes')).toBeInTheDocument();
  expect(screen.getByText('60 → 120 min')).toBeInTheDocument();
  expect(trip.chatlogs.chatdata[0]).toBe(initial);
  await userEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
  expect(screen.queryByText('Review changes')).not.toBeInTheDocument();
  expect(persistTripEdit).not.toHaveBeenCalled();
  expect(trip.chatlogs.chatdata[0]).toBe(initial);
});

it('keeps saved confirmation after applying an explicit save to actual context', async () => {
  const trip = buildUserDataWithRoute({
    duration: 3600,
    distance: 1609,
    stops: [
      { name: 'Old stop', type: 'stop' },
      { name: 'End', type: 'end' },
    ],
  });
  const initial = trip.chatlogs.chatdata[0];
  const result = {
    route: {
      duration: 7200,
      distance: 3218,
      stops: [
        { name: 'New place', type: 'stop' },
        { name: 'End', type: 'end' },
      ],
    },
    itinerary: [],
  };
  loadRouteAlternatives.mockResolvedValue({
    places: [{ id: 'catalog:1', name: 'New place', coordinates: [37, -120] }],
  });
  previewTripEdit.mockResolvedValue(result);
  persistTripEdit.mockImplementation(async (original, snapshot) => ({ status: 'saved', snapshot }));
  renderEditorWithData(trip);
  await userEvent.click(screen.getByRole('button', { name: 'Find places' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Choose New place' }));
  await userEvent.click(screen.getByRole('button', { name: 'Recalculate trip' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Save changes' }));
  expect(await screen.findByText('Trip changes saved.')).toBeInTheDocument();
  expect(trip.chatlogs.chatdata[0]).not.toBe(initial);
  expect(trip.chatlogs.chatdata[0].route).toBe(result.route);
  expect(screen.queryByText('Review changes')).not.toBeInTheDocument();
});
it('shows specific feasibility feedback when recalculation rejects a visit window', async () => {
  loadRouteAlternatives.mockResolvedValue({
    places: [{ id: 'catalog:1', name: 'New place', coordinates: [37, -120] }],
  });
  previewTripEdit.mockRejectedValue({
    response: { data: { detail: 'Attraction closes before the proposed visit.' } },
  });
  renderEditorWithData(buildUserDataWithRoute({ stops: [{ name: 'End', type: 'end' }] }));
  await userEvent.click(screen.getByRole('button', { name: 'Find places' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Choose New place' }));
  await userEvent.click(screen.getByRole('button', { name: 'Recalculate trip' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Attraction closes before the proposed visit.'
  );
});
