/**
 * MapPage — renders map or empty state based on whether a route exists.
 * mapbox-gl and Map component are both stubbed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import React, { useContext } from 'react';
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
