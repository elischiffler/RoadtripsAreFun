import { beforeEach, expect, it, vi } from 'vitest';
import { useContext } from 'react';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
import { ChatData, ChatLogs, Data, UserDataContext } from '../states/UserDataContext';
import TripCarSettings from '../components/TripCarSettings';
import { applyTripCar, saveTripCar, tripCarChoices } from '../services/tripCar';
import { initializeUserData } from '../services/savedTrips';
import axios from '../services/protectedRequest';

vi.mock('../services/protectedRequest', () => ({ default: { put: vi.fn() } }));
vi.mock('../services/savedTrips', () => ({ initializeUserData: vi.fn() }));
const makeTrip = (id = 4) => {
  const trip = new ChatData(id);
  trip.agentChatId = 'original-trip-' + id;
  trip.carDetails = ['2018', 'Toyota', 'Corolla'];
  trip.route = {
    distance: 100,
    geometry: {
      coordinates: [
        [0, 0],
        [1, 1],
      ],
    },
  };
  trip.itinerary = [{ date: '2027-01-01', stops: ['Keep'] }];
  trip.tripProfile = { num_stops: 3, start_address: 'Boulder', destination_address: 'Denver' };
  return trip;
};
let trips;
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  fixtureSession('account-a');
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
  trips = [makeTrip(), makeTrip(5)];
  initializeUserData.mockImplementation(async () => ({
    UserData: new Data(new ChatLogs(trips, 4)),
    chats: [
      { id: 4, title: 'Boulder → Denver' },
      { id: 5, title: 'Other trip' },
    ],
  }));
  axios.put.mockImplementation(async (_, payload) => ({
    data: { car_status: payload.car_status, car: payload.car },
  }));
});
function Probe() {
  const { UserData } = useContext(UserDataContext);
  return <pre data-testid="trip-state">{JSON.stringify(UserData.chatlogs.chatdata)}</pre>;
}

it('uses legacy and structured saved cars while honoring an explicit skip', () => {
  expect(tripCarChoices(makeTrip()).car).toEqual({ year: 2018, make: 'Toyota', model: 'Corolla' });
  const trip = makeTrip();
  trip.tripProfile.car = { year: 2022, make: 'Honda', model: 'Civic' };
  expect(tripCarChoices(trip).car.year).toBe(2022);
  trip.tripProfile.car_status = 'skipped';
  expect(tripCarChoices(trip)).toEqual({ car_status: 'skipped', car: null });
  expect(applyTripCar(trip, { car_status: 'skipped', car: null }).carDetails).toEqual(['', '', '']);
});

it('loads an existing car and saves only that trip without changing route, itinerary or the other trip', async () => {
  renderWithProviders(
    <>
      <TripCarSettings />
      <Probe />
    </>
  );
  expect(await screen.findByLabelText('Car make')).toHaveValue('Toyota');
  await userEvent.clear(screen.getByLabelText('Car make'));
  await userEvent.type(screen.getByLabelText('Car make'), 'Honda');
  await userEvent.click(screen.getByRole('button', { name: 'Save trip car' }));
  await screen.findByText('Trip car saved.');
  expect(axios.put).toHaveBeenCalledWith(
    'http://localhost:8000/chats/4/car',
    {
      car_status: 'provided',
      car: { year: 2018, make: 'Honda', model: 'Corolla' },
      expected_agent_chat_id: 'original-trip-4',
    },
    expect.any(Object)
  );
  const state = JSON.parse(screen.getByTestId('trip-state').textContent);
  expect(state[0].carDetails).toEqual(['2018', 'Honda', 'Corolla']);
  expect(state[0].route).toEqual(trips[0].route);
  expect(state[0].itinerary).toEqual(trips[0].itinerary);
  expect(state[0].tripProfile.num_stops).toBe(3);
  expect(state[1]).toEqual(trips[1]);
  await userEvent.selectOptions(screen.getByLabelText('Trip', { exact: true }), '5');
  expect(screen.getByLabelText('Car make')).toHaveValue('Toyota');
});

it('keeps failed edits for retry and supports removing car details', async () => {
  axios.put.mockRejectedValueOnce(new Error('offline'));
  renderWithProviders(<TripCarSettings />);
  await screen.findByLabelText('Car make');
  await userEvent.click(screen.getByRole('radio', { name: 'No car details' }));
  await userEvent.click(screen.getByRole('button', { name: 'Save trip car' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('radio', { name: 'No car details' })).toBeChecked();
  await userEvent.click(screen.getByRole('button', { name: 'Save trip car' }));
  await screen.findByText('Trip car saved.');
  expect(axios.put.mock.calls[1][1].car).toBeNull();
});

it('reports a deleted/replaced trip and does not change the current snapshot', async () => {
  axios.put.mockRejectedValueOnce({ response: { status: 404 } });
  renderWithProviders(
    <>
      <TripCarSettings />
      <Probe />
    </>
  );
  await screen.findByLabelText('Car make');
  await userEvent.click(screen.getByRole('button', { name: 'Save trip car' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('changed or was deleted');
  expect(JSON.parse(screen.getByTestId('trip-state').textContent)[0].carDetails[1]).toBe('Toyota');
});

it('rejects cross-session save responses and empties car forms on account change', async () => {
  let finish;
  axios.put.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  renderWithProviders(
    <>
      <TripCarSettings />
      <Probe />
    </>
  );
  await screen.findByLabelText('Car make');
  await userEvent.click(screen.getByRole('button', { name: 'Save trip car' }));
  await waitFor(() => expect(finish).toBeTypeOf('function'));
  act(() => signOut());
  await act(async () =>
    finish({ data: { car_status: 'provided', car: { year: 2018, make: 'Other', model: 'Car' } } })
  );
  expect(screen.queryByLabelText('Car make')).not.toBeInTheDocument();
  expect(screen.queryByText('Trip car saved.')).not.toBeInTheDocument();
});

it('retries loading saved trips without making a car or profile mutation', async () => {
  initializeUserData.mockResolvedValueOnce(null);
  renderWithProviders(<TripCarSettings />);
  await screen.findByText('Saved trips could not be loaded.');
  await userEvent.click(screen.getByRole('button', { name: 'Retry loading trip cars' }));
  await screen.findByLabelText('Car make');
  expect(axios.put).not.toHaveBeenCalled();
});

it('passes the original trip identity without route data', async () => {
  await saveTripCar(makeTrip(), { car_status: 'skipped', car: null });
  expect(Object.keys(axios.put.mock.calls[0][1]).sort()).toEqual([
    'car',
    'car_status',
    'expected_agent_chat_id',
  ]);
});
