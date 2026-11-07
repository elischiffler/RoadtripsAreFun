import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { startForegroundArrivals } from '../services/foregroundArrivals';

const now = Date.parse('2026-11-07T12:00:00Z');
let callbacks, stops;
const position = (seconds = 0) => ({
  coords: { latitude: 34, longitude: -118, accuracy: 10, speed: 0 },
  timestamp: now + seconds * 1000,
});
const begin = (overrides = {}) => {
  const options = {
    tripId: 42,
    targets: [{ id: 'park', name: 'Park', coordinates: [34, -118] }],
    onArrival: vi.fn(),
    onStatus: vi.fn(),
    excludedIds: () => new Set(),
    canRecord: () => true,
    isCurrent: () => true,
    ...overrides,
  };
  const stop = startForegroundArrivals(options);
  stops.push(stop);
  return { ...options, stop };
};
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(now);
  callbacks = [];
  stops = [];
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  navigator.geolocation.watchPosition = vi.fn((success, failure) => {
    callbacks.push({ success, failure });
    return callbacks.length;
  });
  navigator.geolocation.clearWatch = vi.fn();
});
afterEach(() => {
  stops.forEach((stop) => stop());
  vi.useRealTimers();
});
const sample = (seconds, callback = callbacks.at(-1)) => {
  vi.setSystemTime(now + seconds * 1000);
  callback.success(position(seconds));
};
it('uses one foreground watch, emits only a versioned arrival, and rejects late callbacks', () => {
  const tracking = begin();
  expect(navigator.geolocation.watchPosition).toHaveBeenCalledWith(
    expect.any(Function),
    expect.any(Function),
    { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
  );
  [0, 20, 40, 60].forEach((seconds) => sample(seconds));
  expect(tracking.onArrival).toHaveBeenCalledTimes(1);
  expect(tracking.onArrival.mock.calls[0][0]).toMatchObject({
    type: 'trip.stop.arrived',
    source: 'web-foreground',
    tripId: 42,
  });
  tracking.stop();
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  sample(80);
  expect(tracking.onArrival).toHaveBeenCalledTimes(1);
});
it('clears on hidden and resets the entire dwell on visible, ignoring callbacks from an old watch', () => {
  const tracking = begin();
  const old = callbacks[0];
  sample(0);
  sample(20);
  Object.defineProperty(document, 'visibilityState', { value: 'hidden' });
  document.dispatchEvent(new Event('visibilitychange'));
  expect(tracking.onStatus).toHaveBeenLastCalledWith({ status: 'paused' });
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  sample(40, old);
  Object.defineProperty(document, 'visibilityState', { value: 'visible' });
  document.dispatchEvent(new Event('visibilitychange'));
  sample(60, old);
  [60, 80, 100].forEach((seconds) => sample(seconds));
  expect(tracking.onArrival).not.toHaveBeenCalled();
  sample(120);
  expect(tracking.onArrival).toHaveBeenCalledTimes(1);
});
it('expires a lost fix instead of leaving a misleading current status', () => {
  const tracking = begin();
  sample(0);
  vi.advanceTimersByTime(10001);
  expect(tracking.onStatus).toHaveBeenLastCalledWith({ status: 'waiting' });
  [30, 50, 70].forEach((seconds) => sample(seconds));
  expect(tracking.onArrival).not.toHaveBeenCalled();
});
it('handles permission denial, watch exceptions, timeout and page exit without retaining a watch', () => {
  const denied = begin();
  callbacks.at(-1).failure({ code: 1 });
  expect(denied.onStatus).toHaveBeenLastCalledWith({ status: 'denied' });
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  const timeout = begin();
  callbacks.at(-1).failure({ code: 3 });
  expect(timeout.onStatus).toHaveBeenLastCalledWith({ status: 'unavailable' });
  const leaving = begin();
  window.dispatchEvent(new Event('pagehide'));
  expect(leaving.onStatus).toHaveBeenLastCalledWith({ status: 'ended' });
  navigator.geolocation.watchPosition.mockImplementationOnce(() => {
    throw new Error('unsupported');
  });
  expect(begin().onStatus).toHaveBeenLastCalledWith({ status: 'unavailable' });
});
it('stops on an account change, ignores renewal in the same session and blocks while saving', () => {
  let current = true,
    saving = true;
  const tracking = begin({ isCurrent: () => current, canRecord: () => !saving });
  window.dispatchEvent(new Event('auth-changed'));
  expect(navigator.geolocation.clearWatch).not.toHaveBeenCalled();
  sample(0);
  expect(tracking.onStatus).toHaveBeenLastCalledWith({ status: 'saving' });
  saving = false;
  sample(20);
  current = false;
  window.dispatchEvent(new Event('auth-changed'));
  expect(tracking.onStatus).toHaveBeenLastCalledWith({ status: 'signed-out' });
  expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(1);
  sample(40);
  expect(tracking.onArrival).not.toHaveBeenCalled();
});
