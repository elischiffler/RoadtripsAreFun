import { useState } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import TripVisitProgress from '../components/TripVisitProgress';
import TripArrivalTracking from '../components/TripArrivalTracking';
import { ChatData, ChatLogs, Data, UserDataContext } from '../states/UserDataContext';
import { updateUserData } from '../services/savedTrips';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
vi.mock('../services/savedTrips', () => ({ updateUserData: vi.fn() }));
const now = Date.parse('2026-11-07T12:00:00Z');
let callbacks;
const trip = () => {
  const data = new ChatData(42);
  data.itinerary = [
    { date: 'Day 1', stops: [{ name: 'Park', kind: 'arrival', provider_id: 'park' }] },
  ];
  data.route = { stops: [{ name: 'Park', provider_id: 'park', coordinates: [34, -118] }] };
  data.presentation = { custom: 'preserve' };
  return data;
};
function Fixture() {
  const [UserData, setUserData] = useState(() => new Data(new ChatLogs([trip()], 42)));
  return (
    <UserDataContext.Provider value={{ UserData, setUserData, chats: [{ id: 42, messages: [] }] }}>
      <TripVisitProgress trip={UserData.chatlogs.chatdata[0]} />
    </UserDataContext.Provider>
  );
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(now);
  fixtureSession();
  callbacks = [];
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  navigator.geolocation.watchPosition = vi.fn((success, failure) => {
    callbacks.push({ success, failure });
    return callbacks.length;
  });
  navigator.geolocation.clearWatch = vi.fn();
  updateUserData.mockReset().mockResolvedValue(true);
});
afterEach(() => {
  vi.useRealTimers();
});
const click = (name) => fireEvent.click(screen.getByRole('button', { name }));
const sample = async (seconds, index = callbacks.length - 1) => {
  await act(async () => {
    vi.setSystemTime(now + seconds * 1000);
    callbacks[index].success({
      timestamp: Date.now(),
      coords: { latitude: 34, longitude: -118, accuracy: 10, speed: 0 },
    });
  });
};
const arrive = async (start = 0) => {
  for (const second of [start, start + 20, start + 40, start + 60]) await sample(second);
};
it('requests no location before opt-in, then detects and saves once without transmitting raw fixes', async () => {
  const view = render(<Fixture />);
  expect(navigator.geolocation.watchPosition).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'Mark visited: Park' })).not.toBeInTheDocument();
  expect(screen.getByText(/not in the background/)).toBeInTheDocument();
  click('Enable automatic arrivals');
  expect(navigator.geolocation.watchPosition).toHaveBeenCalledTimes(1);
  await arrive();
  expect(screen.getByText('1 of 1 stops visited')).toBeInTheDocument();
  expect(screen.getByText('Visit updates saved.')).toBeInTheDocument();
  const presentation = updateUserData.mock.calls[0][1].presentation;
  expect(presentation.custom).toBe('preserve');
  expect(Object.values(presentation.arrivals)[0]).toMatchObject({
    source: 'web-foreground',
    dwellSeconds: 60,
  });
  expect(JSON.stringify(presentation)).not.toMatch(/latitude|longitude/);
  await sample(80);
  await sample(100);
  expect(updateUserData).toHaveBeenCalledTimes(1);
  click('Correct an arrival');
  click('Undo visited: Park');
  await act(async () => {});
  await arrive(120);
  expect(screen.getByText('0 of 1 stops visited')).toBeInTheDocument();
  expect(updateUserData).toHaveBeenCalledTimes(2);
  click('Turn off automatic arrivals');
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  view.unmount();
});
it('keeps failed arrival local, pauses tracking and retries the same metadata', async () => {
  updateUserData.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  render(<Fixture />);
  click('Enable automatic arrivals');
  await arrive();
  expect(screen.getByText(/could not be saved/)).toBeInTheDocument();
  expect(screen.getByText(/paused until your visit updates/)).toBeInTheDocument();
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  click('Correct an arrival');
  expect(screen.getByRole('button', { name: 'Undo visited: Park' })).toBeDisabled();
  click('Retry saving visits');
  await act(async () => {});
  expect(screen.getByText('Visit updates saved.')).toBeInTheDocument();
  expect(updateUserData.mock.calls[1][1].presentation).toEqual(
    updateUserData.mock.calls[0][1].presentation
  );
  expect(navigator.geolocation.watchPosition).toHaveBeenCalledTimes(2);
});
it('preserves a conflict and requires reload rather than retrying or continuing tracking', async () => {
  updateUserData.mockImplementation(async (_token, snapshot) => {
    snapshot.saveConflict = true;
    return false;
  });
  render(<Fixture />);
  click('Enable automatic arrivals');
  await arrive();
  expect(screen.getByText(/This saved trip changed/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Retry saving visits' })).not.toBeInTheDocument();
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  await sample(80, 0);
  expect(updateUserData).toHaveBeenCalledTimes(1);
});
it('stops on denial, errors, sign-out and unmount, and permits explicit retry', async () => {
  const view = render(<Fixture />);
  click('Enable automatic arrivals');
  act(() => callbacks[0].failure({ code: 1 }));
  expect(screen.getByText(/Location permission was not granted/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Enable automatic arrivals' })).toBeInTheDocument();
  click('Enable automatic arrivals');
  act(() => callbacks[1].failure({ code: 2 }));
  expect(screen.getByText(/Location is unavailable/)).toBeInTheDocument();
  click('Enable automatic arrivals');
  act(() => signOut());
  expect(screen.getByText(/sign-in changed/)).toBeInTheDocument();
  await sample(60, 2);
  expect(updateUserData).not.toHaveBeenCalled();
  view.unmount();
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(3);
});
it('disables unavailable or unmapped tracking and restarts safely on route identity changes', async () => {
  const props = { trip: trip(), onArrival: vi.fn(), canRecord: () => true, blocked: false };
  const view = render(<TripArrivalTracking {...props} />);
  click('Enable automatic arrivals');
  await sample(0);
  await sample(20);
  view.rerender(
    <TripArrivalTracking
      {...props}
      trip={{
        ...props.trip,
        itinerary: [{ stops: [{ name: 'Another', coordinates: [35, -117] }] }],
      }}
    />
  );
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  await sample(40, 0);
  expect(props.onArrival).not.toHaveBeenCalled();
  view.rerender(
    <TripArrivalTracking {...props} trip={{ ...props.trip, route: {}, itinerary: [] }} />
  );
  expect(screen.getByText(/no verified stop coordinates/)).toBeInTheDocument();
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(2);
  expect(navigator.geolocation.watchPosition).toHaveBeenCalledTimes(2);
  expect(screen.getByRole('button', { name: 'Turn off automatic arrivals' })).toBeEnabled();
  click('Turn off automatic arrivals');
  expect(screen.getByRole('button', { name: 'Enable automatic arrivals' })).toBeDisabled();
  view.unmount();
  navigator.geolocation.watchPosition = undefined;
  render(<TripArrivalTracking {...props} />);
  expect(screen.getByRole('button', { name: 'Enable automatic arrivals' })).toBeDisabled();
});
