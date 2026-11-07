import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton } from '../design';
import { getSession, isCurrentSession } from '../services/session';
import { arrivalTargets, automaticArrivalExcludedStopIds } from '../services/tripArrivals';
import { startForegroundArrivals } from '../services/foregroundArrivals';
import { visitedStopIds } from '../services/tripPresentation';

const messages = {
  off: 'Automatic arrivals are off.',
  waiting: 'Waiting for a fresh, accurate location…',
  watching: 'Checking for arrivals while this page is visible.',
  moving: 'On the move. Passing a stop does not mark an arrival.',
  ambiguous: 'Nearby stops are too close to distinguish. Use the correction option if needed.',
  paused: 'Paused while this page is hidden. Keep it open for automatic arrivals.',
  denied:
    'Location permission was not granted. You can allow it in browser settings or correct arrivals manually.',
  unavailable: 'Location is unavailable. Try again or correct arrivals manually.',
  saving: 'Waiting for the previous arrival update to save.',
  ended: 'Arrival tracking stopped when you left this page. Enable it again to continue.',
  'signed-out': 'Arrival tracking stopped because your sign-in changed.',
};

export default function TripArrivalTracking({ trip, onArrival, canRecord, blocked }) {
  const [enabled, setEnabled] = useState(false);
  const [state, setState] = useState({ status: 'off' });
  const latest = useRef({ trip, onArrival, canRecord });
  latest.current = { trip, onArrival, canRecord };
  // A route/edit change invalidates the old dwell without reacting to arrival saves.
  const targetKey = JSON.stringify(arrivalTargets(trip));
  const supported =
    window.isSecureContext !== false && typeof navigator.geolocation?.watchPosition === 'function';
  useEffect(() => {
    if (!enabled || blocked || !supported || targetKey === '[]') return;
    const session = getSession();
    return startForegroundArrivals({
      tripId: trip.chatId,
      targets: JSON.parse(targetKey),
      isCurrent: () => isCurrentSession(session) && Boolean(getSession().accessToken),
      canRecord: () => latest.current.canRecord(),
      excludedIds: () =>
        new Set([
          ...visitedStopIds(latest.current.trip.presentation),
          ...automaticArrivalExcludedStopIds(latest.current.trip.presentation),
        ]),
      onArrival: (event) => latest.current.onArrival(event),
      onStatus: (next) => {
        setState(next);
        if (['denied', 'unavailable', 'signed-out', 'ended'].includes(next.status))
          setEnabled(false);
      },
    });
  }, [enabled, blocked, supported, trip.chatId, targetKey]);
  const targets = JSON.parse(targetKey);
  const toggle = () => {
    setEnabled((value) => !value);
    if (enabled) setState({ status: 'off' });
  };
  return (
    <section className="trip-arrival-tracking" aria-label="Automatic arrivals">
      <p className="rt-title">Automatic arrivals</p>
      <p className="rt-caption" id={`arrival-privacy-${trip.chatId}`}>
        Allow location to detect a stop after about a minute nearby. Works only while this page is
        open and visible, not in the background or with your screen locked. Your position stays on
        this device; only arrival records (stop, time and detection quality) are saved to your
        account.
      </p>
      <ActionButton
        variant={enabled ? 'secondary' : 'primary'}
        onClick={toggle}
        disabled={!enabled && (!supported || !targets.length || blocked)}
        aria-describedby={`arrival-privacy-${trip.chatId}`}
      >
        {enabled ? 'Turn off automatic arrivals' : 'Enable automatic arrivals'}
      </ActionButton>
      <p className="rt-caption" role="status">
        {!supported
          ? 'Location tracking is not available in this browser. Use a secure browser or correct arrivals manually.'
          : !targets.length
            ? 'This itinerary has no verified stop coordinates. Correct arrivals manually.'
            : blocked
              ? 'Automatic arrivals are paused until your visit updates are saved or the trip is reloaded.'
              : state.status === 'dwelling'
                ? `Near ${state.name}. Waiting to confirm you have stopped…`
                : state.status === 'arrived'
                  ? `Arrival detected at ${state.name}.`
                  : messages[state.status]}
      </p>
    </section>
  );
}
TripArrivalTracking.propTypes = {
  trip: PropTypes.object.isRequired,
  onArrival: PropTypes.func.isRequired,
  canRecord: PropTypes.func.isRequired,
  blocked: PropTypes.bool.isRequired,
};
