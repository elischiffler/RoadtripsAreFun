/**
 * ItineraryPage — renders day cards or the empty-state message.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import React from 'react';
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
import ItineraryPage from '../pages/ItineraryPage/ItineraryPage';

function renderItineraryPageWithData(UserData) {
  function Wrapper({ children }) {
    return (
      <UserDataProvider>
        <ThemeProvider theme={customTheme}>
          <MemoryRouter initialEntries={['/itinerary']}>
            <UserDataContext.Provider
              value={{
                UserData,
                setUserData: vi.fn(),
                chats: [],
                setChats: vi.fn(),
                currentStep: 5,
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
  return render(<ItineraryPage />, { wrapper: Wrapper });
}

const MOCK_ITINERARY = [
  {
    date: 'Day 1 — Monday June 7',
    stops: [
      { name: 'Depart Denver', time: '8:00 AM', address: null, url: null, price: null },
      {
        name: 'Red Rocks Park',
        time: '9:30 AM',
        address: '18300 W Alameda Pkwy, Morrison, CO',
        url: 'https://redrocks.com',
        price: 12,
      },
    ],
  },
  {
    date: 'Day 2 — Tuesday June 8',
    stops: [
      {
        name: 'Hotel Check-in',
        time: '3:00 PM',
        address: '123 Main St, Colorado Springs, CO',
        url: null,
        price: 150,
      },
    ],
  },
];

function buildUserDataWithItinerary(itinerary) {
  const cd = new ChatData(1);
  cd.itinerary = itinerary;
  const logs = new ChatLogs([cd], 1);
  return new Data(logs);
}

describe('ItineraryPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows "No Itinerary Available" when there is no itinerary', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(null));
    expect(screen.getByText(/no itinerary available/i)).toBeInTheDocument();
  });

  it('renders day headers from the itinerary', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(MOCK_ITINERARY));
    expect(screen.getByText('Day 1 — Monday June 7')).toBeInTheDocument();
    expect(screen.getByText('Day 2 — Tuesday June 8')).toBeInTheDocument();
  });

  it('renders stop names', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(MOCK_ITINERARY));
    expect(screen.getByText('Depart Denver')).toBeInTheDocument();
    expect(screen.getByText('Red Rocks Park')).toBeInTheDocument();
    expect(screen.getByText('Hotel Check-in')).toBeInTheDocument();
  });

  it('renders a clickable link for stops with a URL', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(MOCK_ITINERARY));
    const link = screen.getByRole('link', { name: /red rocks park/i });
    expect(link).toHaveAttribute('href', 'https://redrocks.com');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('shows an address for stops that have one', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(MOCK_ITINERARY));
    expect(screen.getByText(/18300 W Alameda Pkwy/)).toBeInTheDocument();
  });

  it('shows price when present', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(MOCK_ITINERARY));
    expect(screen.getByText(/price: \$12/i)).toBeInTheDocument();
  });

  it('shows "Departure time" for stops without an address', () => {
    renderItineraryPageWithData(buildUserDataWithItinerary(MOCK_ITINERARY));
    expect(screen.getByText(/departure time: 8:00 AM/i)).toBeInTheDocument();
  });
});
