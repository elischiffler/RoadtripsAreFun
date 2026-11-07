import { useState } from 'react';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import TripArrivalTracking from '../components/TripArrivalTracking';
import TripVisitProgress from '../components/TripVisitProgress';
import { ChatData, ChatLogs, Data, UserDataContext } from '../states/UserDataContext';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
import { updateUserData } from '../services/savedTrips';
vi.mock('../services/savedTrips', async (original) => ({
  ...(await original()),
  updateUserData: vi.fn(),
}));
const base = Date.parse('2030-05-04T12:00:00Z');
const makeTrip = (twoStops = false) => {
  const trip = new ChatData(731);
  const stop = {
    provider_id: 'place:arrival',
    name: 'Arrival garden',
    type: 'stop',
    kind: 'arrival',
    arrival_time: '2030-05-04T12:00:00Z',
    departure_time: '2030-05-04T12:45:00Z',
    coordinates: [40, -105],
  };
  const stops = twoStops
    ? [
        stop,
        {
          ...stop,
          provider_id: 'place:second',
          name: 'Second garden',
          coordinates: [40.00054, -105],
          arrival_time: '2030-05-04T12:45:00Z',
          departure_time: '2030-05-04T13:30:00Z',
        },
      ]
    : [stop];
  trip.route = { departure_time: '2030-05-04T11:00:00Z', stops };
  trip.itinerary = [
    { date: 'Today', stops: stops.map((item) => ({ ...item, coordinates: undefined })) },
  ];
  trip.presentation = { futureField: 'preserve' };
  trip.savedRevision = 'a'.repeat(64);
  return trip;
};
let success, failure, clearWatch, watchPosition;
const descriptors = [
  [navigator, 'geolocation'],
  [window, 'isSecureContext'],
  [document, 'visibilityState'],
].map(([object, key]) => [object, key, Object.getOwnPropertyDescriptor(object, key)]);
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(base);
  vi.clearAllMocks();
  fixtureSession();
  clearWatch = vi.fn();
  watchPosition = vi.fn((ok, error) => {
    success = ok;
    failure = error;
    return 17;
  });
  navigator.geolocation = { watchPosition, clearWatch };
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
  updateUserData.mockResolvedValue(true);
});
afterEach(() => {
  vi.useRealTimers();
  for (const [object, key, descriptor] of descriptors) {
    if (descriptor) Object.defineProperty(object, key, descriptor);
    else delete object[key];
  }
});
const enable = () =>
  userEvent.click(
    screen.getByRole('button', { name: 'Enable location and mark nearby stops visited' })
  );
const send = async (offset, changes = {}) => {
  await act(async () => {
    vi.setSystemTime(base + offset);
    success({
      timestamp: Date.now(),
      coords: { latitude: 40, longitude: -105, accuracy: 10, speed: 0, ...changes },
    });
  });
};
const dwell = async () => {
  for (const offset of [0, 15000, 30000, 45000, 60000]) await send(offset);
};
function Fixture(options = {}) {
  const twoStops = options.twoStops === true;
  const [UserData, setUserData] = useState(() => new Data(new ChatLogs([makeTrip(twoStops)], 731)));
  return (
    <UserDataContext.Provider value={{ UserData, setUserData, chats: [{ id: 731, messages: [] }] }}>
      <TripVisitProgress trip={UserData.chatlogs.chatdata[0]} />
    </UserDataContext.Provider>
  );
}
it('opts in explicitly, automatically saves one detected visit and supports immediate undo', async () => {
  render(<Fixture />);
  expect(watchPosition).not.toHaveBeenCalled();
  await enable();
  expect(watchPosition).toHaveBeenCalledWith(expect.any(Function), expect.any(Function), {
    enableHighAccuracy: true,
    maximumAge: 0,
    timeout: 15000,
  });
  await send(0, { accuracy: 1000 });
  expect(updateUserData).not.toHaveBeenCalled();
  for (const offset of [1000, 16000, 31000, 46000, 61000]) await send(offset);
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(screen.getByText('1 of 1 stops visited')).toBeInTheDocument();
  expect(screen.getByText('Detected arrival: Arrival garden')).toBeInTheDocument();
  expect(updateUserData).toHaveBeenCalledTimes(1);
  const saved = updateUserData.mock.calls[0][1];
  expect(saved.presentation).toMatchObject({
    futureField: 'preserve',
    visitedStopIds: [expect.any(String)],
    arrivals: expect.any(Object),
  });
  expect(JSON.stringify(saved.presentation)).not.toMatch(/latitude|longitude/);
  expect(saved.savedRevision).toBe('a'.repeat(64));
  expect(updateUserData.mock.calls[0][4]).toEqual({ presentationOnly: true });
  await send(76000);
  expect(updateUserData).toHaveBeenCalledTimes(1);
  await userEvent.click(
    screen.getByRole('button', { name: 'Undo detected visit: Arrival garden' })
  );
  expect(screen.getByText('0 of 1 stops visited')).toBeInTheDocument();
  expect(updateUserData.mock.calls[1][1].presentation.visitedStopIds).toEqual([]);
  expect(clearWatch).toHaveBeenCalledWith(17);
});
it('preserves the departure latch and watch through actual auto-save/next-target rerenders', async () => {
  let revision = 0;
  updateUserData.mockImplementation(async (_token, snapshot) => {
    snapshot.savedRevision = String(++revision).repeat(64);
    return true;
  });
  render(<Fixture twoStops />);
  await enable();
  await dwell();
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(screen.getByText('Next attraction: Second garden')).toBeInTheDocument();
  expect(watchPosition).toHaveBeenCalledTimes(1);
  expect(clearWatch).not.toHaveBeenCalled();
  for (const offset of [75000, 90000, 105000, 120000]) await send(offset);
  expect(updateUserData).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Leave this arrival area/)).toBeInTheDocument();
  await send(135000, { latitude: 40.003 });
  await send(150000, { latitude: 40.003 });
  await send(165000, { latitude: 40.00054 });
  for (const offset of [180000, 195000, 210000, 225000, 240000])
    await send(offset, { latitude: 40.00054 });
  expect(await screen.findByText('2 of 2 stops visited')).toBeInTheDocument();
  expect(updateUserData).toHaveBeenCalledTimes(2);
  expect(watchPosition).toHaveBeenCalledTimes(1);
  expect(clearWatch).toHaveBeenCalledWith(17);
});
it('does not claim a failed detected visit was saved and never replays a stale conflict', async () => {
  updateUserData.mockImplementation(async (_token, snapshot) => {
    snapshot.saveConflict = true;
    return false;
  });
  render(<Fixture />);
  await enable();
  await dwell();
  expect(await screen.findByText(/This saved trip changed/)).toBeInTheDocument();
  expect(screen.queryByText('Visit updates saved.')).not.toBeInTheDocument();
  expect(clearWatch).toHaveBeenCalledWith(17);
  expect(
    screen.getByRole('button', { name: 'Enable location and mark nearby stops visited' })
  ).toBeDisabled();
  await send(75000);
  expect(updateUserData).toHaveBeenCalledTimes(1);
});
it('keeps failed automatic writes local and uses the existing explicit retry', async () => {
  updateUserData.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<Fixture />);
  await enable();
  await dwell();
  expect(await screen.findByText(/could not be saved/)).toBeInTheDocument();
  expect(clearWatch).toHaveBeenCalledWith(17);
  await userEvent.click(screen.getByRole('button', { name: 'Retry saving visits' }));
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
  expect(updateUserData).toHaveBeenCalledTimes(2);
  expect(watchPosition).toHaveBeenCalledTimes(1);
});
it('stops on denial, supports manual fallback and ignores late callbacks', async () => {
  render(<Fixture />);
  await enable();
  act(() => failure({ code: 1 }));
  expect(screen.getByText(/Location permission was denied/)).toBeInTheDocument();
  expect(clearWatch).toHaveBeenCalledWith(17);
  await dwell();
  expect(updateUserData).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Correct an arrival' }));
  await userEvent.click(screen.getByRole('button', { name: 'Mark visited: Arrival garden' }));
  expect(await screen.findByText('Visit updates saved.')).toBeInTheDocument();
});
it('clears location on hide and requires explicit restart when visible again', async () => {
  render(<Fixture />);
  await enable();
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
  act(() => document.dispatchEvent(new Event('visibilitychange')));
  expect(clearWatch).toHaveBeenCalledWith(17);
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
  act(() => document.dispatchEvent(new Event('visibilitychange')));
  await dwell();
  expect(updateUserData).not.toHaveBeenCalled();
  expect(watchPosition).toHaveBeenCalledTimes(1);
});
it('stops on route changes, account changes and unmount', async () => {
  const callbacks = { onArrival: vi.fn(), onUndo: vi.fn(), canRecord: () => true, blocked: false };
  const first = makeTrip();
  const view = render(<TripArrivalTracking trip={first} {...callbacks} />);
  await enable();
  view.rerender(
    <TripArrivalTracking trip={{ ...first, route: { ...first.route } }} {...callbacks} />
  );
  expect(clearWatch).toHaveBeenCalledWith(17);
  await dwell();
  expect(callbacks.onArrival).not.toHaveBeenCalled();
  await enable();
  act(() => signOut());
  await dwell();
  expect(callbacks.onArrival).not.toHaveBeenCalled();
  fixtureSession();
  await enable();
  view.unmount();
  expect(clearWatch).toHaveBeenCalledWith(17);
});
it('handles insecure connections and unavailable fixes', async () => {
  const view = render(
    <TripArrivalTracking
      trip={makeTrip()}
      onArrival={vi.fn()}
      onUndo={vi.fn()}
      canRecord={() => true}
      blocked={false}
    />
  );
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false });
  await enable();
  expect(watchPosition).not.toHaveBeenCalled();
  expect(screen.getByText(/secure connection/)).toBeInTheDocument();
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
  view.rerender(
    <TripArrivalTracking
      trip={makeTrip()}
      onArrival={vi.fn()}
      onUndo={vi.fn()}
      canRecord={() => true}
      blocked={false}
    />
  );
  await enable();
  act(() => failure({ code: 2 }));
  expect(screen.getByText(/Location is unavailable/)).toBeInTheDocument();
  expect(clearWatch).toHaveBeenCalledWith(17);
});

it('stops when the account token expires before a fix can be recorded', async () => {
  render(<Fixture />);
  await enable();
  await send(3601000);
  expect(clearWatch).toHaveBeenCalledWith(17);
  expect(screen.getByText(/sign-in changed/)).toBeInTheDocument();
  expect(updateUserData).not.toHaveBeenCalled();
});
