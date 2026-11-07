import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton } from '../design';
import { getSession, hasUsableSession, isCurrentSession } from '../services/session';
import { arrivalTargets, automaticArrivalExcludedStopIds } from '../services/tripArrivals';
import { startForegroundArrivals } from '../services/foregroundArrivals';
import { visitedStopIds } from '../services/tripPresentation';
const messages = {
  off: 'Automatic arrivals are off.',
  waiting: 'Waiting for a fresh, accurate location…',
  watching: 'Checking the next attraction while this page is visible.',
  moving: 'Waiting until you have stopped near the next attraction.',
  ambiguous: 'Nearby stops are too close to distinguish. Correct this arrival manually.',
  departure: 'Leave this arrival area before another nearby attraction can be detected.',
  schedule: 'Arrival checks wait until near this stop’s planned travel time.',
  paused: 'Arrival checks paused when this page was hidden. Enable them again to continue.',
  denied: 'Location permission was denied. Arrival checks are off; manual corrections still work.',
  unavailable:
    'Location is unavailable. Arrival checks are off; start again or correct arrivals manually.',
  saving: 'Waiting for the previous visit update to save.',
  ended: 'Arrival checks stopped. Enable them again to continue.',
  'signed-out': 'Arrival checks stopped because your sign-in changed.',
  done: 'No next attraction is available. Arrival checks stopped.',
};
export default function TripArrivalTracking({ trip, onArrival, onUndo, canRecord, blocked }) {
  const [enabled, setEnabled] = useState(false);
  const [state, setState] = useState({ status: 'off' });
  const [detected, setDetected] = useState(null);
  const consent = useRef(null);
  const latest = useRef(null);
  latest.current = { trip, onArrival, canRecord };
  const targets = arrivalTargets(trip);
  const targetKey = JSON.stringify(targets);
  const excluded = new Set([
    ...visitedStopIds(trip.presentation),
    ...automaticArrivalExcludedStopIds(trip.presentation),
  ]);
  const next = targets.find((target) => !excluded.has(target.id));
  const hasNext = Boolean(next);
  const supported =
    window.isSecureContext === true &&
    typeof navigator.geolocation?.watchPosition === 'function' &&
    typeof navigator.geolocation?.clearWatch === 'function';
  useEffect(() => {
    setEnabled(false);
    setDetected(null);
    setState({ status: 'off' });
  }, [trip.chatId, trip.agentChatId, trip.route]);
  useEffect(() => {
    if (blocked || !hasNext) setEnabled(false);
  }, [blocked, hasNext]);
  useEffect(() => {
    if (
      !enabled ||
      blocked ||
      !supported ||
      targetKey === '[]' ||
      consent.current?.route !== trip.route ||
      consent.current?.chatId !== trip.chatId
    )
      return;
    const session = getSession();
    return startForegroundArrivals({
      tripId: trip.chatId,
      targets: JSON.parse(targetKey),
      isCurrent: () =>
        isCurrentSession(session) &&
        hasUsableSession() &&
        latest.current.trip.route === consent.current?.route &&
        latest.current.trip.chatId === consent.current?.chatId,
      canRecord: () => latest.current.canRecord(),
      excludedIds: () =>
        new Set([
          ...visitedStopIds(latest.current.trip.presentation),
          ...automaticArrivalExcludedStopIds(latest.current.trip.presentation),
        ]),
      onArrival: (event) => latest.current.onArrival(event),
      onStatus: (result) => {
        setState(result);
        if (result.status === 'arrived')
          setDetected({ id: result.arrival.stopId, name: result.name });
        if (
          ['denied', 'unavailable', 'signed-out', 'ended', 'paused', 'done'].includes(result.status)
        )
          setEnabled(false);
      },
    });
  }, [enabled, blocked, supported, trip.chatId, trip.route, targetKey]);
  const canUndo = detected && visitedStopIds(trip.presentation).has(detected.id);
  return (
    <section className="rt-sheet rt-stack" aria-label="Automatic arrivals">
      <h2 className="rt-title">Automatic arrivals</h2>
      <p className="rt-caption">
        With permission, the next attraction is marked visited after about a minute nearby. Checks
        run only while this page is visible, never in the background or with the screen locked. The
        app does not save or share raw location. Your account saves only the stop, arrival time and
        detection quality.
      </p>
      {next && <p className="rt-caption">Next attraction: {next.name}</p>}
      <p className="rt-caption" role="status">
        {!supported
          ? 'Arrival checks need location support and a secure connection. Manual corrections still work.'
          : !targets.length
            ? 'No attraction has matching route coordinates and timing. Correct arrivals manually.'
            : blocked
              ? 'Arrival checks stopped. Resolve the unsaved visit update before starting again.'
              : state.status === 'dwelling'
                ? `Near ${state.name}. Checking that you stay before marking this stop visited.`
                : state.status === 'arrived'
                  ? `Arrival detected at ${state.name}.`
                  : messages[state.status]}
      </p>
      {detected && <p className="rt-caption">Detected arrival: {detected.name}</p>}
      <ActionButton
        variant="secondary"
        disabled={!enabled && (!supported || !next || blocked)}
        onClick={() => {
          if (enabled) {
            setEnabled(false);
            setState({ status: 'off' });
          } else {
            consent.current = { route: trip.route, chatId: trip.chatId };
            setEnabled(true);
          }
        }}
      >
        {enabled ? 'Stop arrival checks' : 'Enable location and mark nearby stops visited'}
      </ActionButton>
      {canUndo && (
        <ActionButton
          variant="secondary"
          disabled={!canRecord() || blocked}
          onClick={() => {
            setEnabled(false);
            setState({ status: 'off' });
            onUndo(detected.id);
            setDetected(null);
          }}
        >
          Undo detected visit: {detected.name}
        </ActionButton>
      )}
    </section>
  );
}
TripArrivalTracking.propTypes = {
  trip: PropTypes.object.isRequired,
  onArrival: PropTypes.func.isRequired,
  onUndo: PropTypes.func.isRequired,
  canRecord: PropTypes.func.isRequired,
  blocked: PropTypes.bool.isRequired,
};
