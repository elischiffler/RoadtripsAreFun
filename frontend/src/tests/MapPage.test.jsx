/**
 * MapPage — renders map or empty state based on whether a route exists.
 * mapbox-gl and Map component are both stubbed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
import MapPage from '../pages/MapPage/MapPage';

vi.mock('../services/routeAlternatives', () => ({ loadRouteAlternatives: vi.fn() }));

// Stub the Map component — it needs real Mapbox tokens and a DOM canvas
vi.mock('../components/Map', () => ({
  default: () => <div data-testid="map-stub">Map Stub</div>,
}));

// MapPage reads UserData from context — we need to inject custom context values.
function renderMapPageWithData(UserData) {
  function Wrapper({ children }) {
    return (
      <UserDataProvider>
        <ThemeProvider theme={customTheme}>
          <MemoryRouter initialEntries={['/map']}>
            <UserDataContext.Provider
              value={{
                UserData,
                setUserData: vi.fn(),
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
  return render(<MapPage />, { wrapper: Wrapper });
}

// Helper — build a UserData with a route on the current chat
function buildUserDataWithRoute(route = null) {
  const cd = new ChatData(1);
  cd.route = route;
  const logs = new ChatLogs([cd], 1);
  return new Data(logs);
}

describe('MapPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows "No Route Available" when there is no route', () => {
    renderMapPageWithData(buildUserDataWithRoute(null));
    expect(screen.getByText(/no route available/i)).toBeInTheDocument();
  });

  it('renders without crashing when a route is present', () => {
    // Map component is stubbed above — just verify MapPage renders the stub
    const fakeRoute = { waypoints: [], distance: 100, duration: 3600 };
    renderMapPageWithData(buildUserDataWithRoute(fakeRoute));
    expect(screen.getByTestId('map-stub')).toBeInTheDocument();
  });
});

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
        url: 'https://example.test/forest',
      },
    ],
    notice: 'Check detour timing',
  });
  renderMapPageWithData(buildUserDataWithRoute(route));
  await userEvent.click(screen.getByRole('button', { name: 'Find nearby ideas' }));
  expect(await screen.findByText('Forest')).toBeInTheDocument();
  expect(loadRouteAlternatives).toHaveBeenCalledWith(route, expect.any(AbortSignal));
  expect(screen.getByText('Source: Fixture catalog')).toBeInTheDocument();
  expect(screen.getByText(/unscheduled suggestions/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'View on map: Forest' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Place information: Forest' })).toHaveAttribute(
    'href',
    'https://example.test/forest'
  );
  expect(route.stops).toEqual([]);
});
it('shows an error and retries failed nearby lookup', async () => {
  loadRouteAlternatives
    .mockRejectedValueOnce(new Error('unavailable'))
    .mockResolvedValueOnce({ places: [], notice: '' });
  renderMapPageWithData(buildUserDataWithRoute({ stops: [] }));
  await userEvent.click(screen.getByRole('button', { name: 'Find nearby ideas' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
  await userEvent.click(screen.getByRole('button', { name: 'Retry nearby ideas' }));
  await waitFor(() =>
    expect(screen.getByRole('status')).toHaveTextContent('No nearby ideas were found')
  );
});
