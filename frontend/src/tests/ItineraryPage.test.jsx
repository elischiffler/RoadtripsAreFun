/**
 * ItineraryPage — renders day cards or the empty-state message.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
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

  Wrapper.propTypes = { children: PropTypes.node.isRequired };
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

  it('shows children and separate room quotes without promising combined inventory', () => {
    const room_offers = [
      { room: { adults: 2, child_ages: [5] }, price: 120, url: 'https://example.test/room-family' },
      { room: { adults: 1, child_ages: [] }, price: 175, url: 'https://example.test/room-solo' },
    ];
    renderItineraryPageWithData(
      buildUserDataWithItinerary([
        {
          date: 'Day 1',
          stops: [{ name: 'Hotel', time: '4 PM', address: 'Main St', price: 295, room_offers }],
        },
      ])
    );
    expect(screen.getByText('Sum of independent room quotes: $295')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Room 1: 2 adults, children aged 5/ })).toHaveAttribute(
      'href',
      room_offers[0].url
    );
    expect(screen.getByRole('link', { name: /Room 2: 1 adults, no children/ })).toHaveAttribute(
      'href',
      room_offers[1].url
    );
    expect(
      screen.getByText('Confirm simultaneous room availability with the booking provider.')
    ).toBeInTheDocument();
  });

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

  it('shows tentative evening options after reload without claiming an arrival time', () => {
    const itinerary = JSON.parse(JSON.stringify(MOCK_ITINERARY));
    itinerary[1].stops.push({
      name: 'Nearby cafe',
      time: 'Unscheduled',
      optional: true,
      kind: 'evening',
      status: 'tentative',
      url: 'https://example.test/cafe',
      notice: 'Check opening hours',
      return_by: '08:00 PM',
    });
    renderItineraryPageWithData(buildUserDataWithItinerary(itinerary));
    expect(screen.getByText(/optional evening suggestion/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Nearby cafe' })).toHaveAttribute(
      'href',
      'https://example.test/cafe'
    );
    expect(screen.getByText('Check opening hours')).toBeInTheDocument();
    expect(screen.getByText('Return to hotel by: 08:00 PM')).toBeInTheDocument();
    expect(screen.queryByText(/Unscheduled/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Suggested visit/)).not.toBeInTheDocument();
  });

  it('shows local actual hotel arrival, late check-in notice and optional visit times', () => {
    const itinerary = [
      {
        date: 'November 21',
        stops: [
          {
            name: 'Hotel',
            kind: 'arrival',
            time: '11:59 PM',
            timezone: 'America/Los_Angeles',
            notice: 'Confirm late check-in with the hotel',
            price: 150,
          },
          {
            name: 'Fixture gallery',
            optional: true,
            kind: 'evening',
            time: '06:40 PM',
            return_time: '07:50 PM',
            return_by: '08:00 PM',
          },
        ],
      },
    ];
    renderItineraryPageWithData(buildUserDataWithItinerary(itinerary));
    expect(screen.getByText('Arrival time: 11:59 PM (America/Los_Angeles)')).toBeInTheDocument();
    expect(screen.getByText('Confirm late check-in with the hotel')).toBeInTheDocument();
    expect(screen.getByText('Suggested visit: 06:40 PM')).toBeInTheDocument();
    expect(screen.getByText('Suggested return: 07:50 PM')).toBeInTheDocument();
    expect(screen.getByText('Price: $150')).toBeInTheDocument();
  });
});
