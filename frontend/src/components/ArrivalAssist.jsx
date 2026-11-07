import { useCallback, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton } from '../design';
import { createArrivalTracker, nextArrivalTarget } from '../services/arrivalAssist';
import { getSession, isCurrentSession } from '../services/session';
import { visitedStopIds } from '../services/tripPresentation';

const MESSAGES = {
  freshness: 'Waiting for a fresh location. Stops are not marked from old readings.',
  accuracy: 'Location is not accurate enough yet. You can still mark visits manually.',
  moving: 'Waiting until you have stopped near the next attraction.',
  departure: 'Leave this arrival area before another nearby attraction can be detected.',
  distance: 'Checking for your next attraction while this page is visible.',
  schedule: 'Arrival checks wait until near this stop’s planned travel time.',
  dwell: 'You appear nearby. Checking that you stay before marking this stop visited.',
  target: 'No next attraction with verified coordinates and timing is available.',
};
export default function ArrivalAssist({ trip, busy = false, blocked = false, onArrived, onUndo }) {
  const [active, setActive] = useState(false);
  const [message, setMessage] = useState('Arrival checks are off.');
  const [detected, setDetected] = useState(null);
  const watch = useRef(null);
  const tracker = useRef(null);
  const current = useRef(null);
  const generation = useRef(0);
  const target = nextArrivalTarget(trip);
  current.current = { target, busy, blocked, onArrived, route: trip.route, chatId: trip.chatId };
  const clear = useCallback(() => {
    generation.current++;
    if (watch.current !== null) navigator.geolocation?.clearWatch?.(watch.current);
    watch.current = null;
    tracker.current = null;
  }, []);
  const stop = useCallback(
    (text) => {
      clear();
      setActive(false);
      if (text) setMessage(text);
    },
    [clear]
  );
  useEffect(() => {
    const hidden = () => {
      if (document.visibilityState !== 'visible')
        stop('Arrival checks stopped while this page was hidden.');
    };
    const leaving = () => stop('Arrival checks stopped.');
    const changed = () => stop('Arrival checks stopped because your account session changed.');
    document.addEventListener('visibilitychange', hidden);
    window.addEventListener('pagehide', leaving);
    window.addEventListener('auth-changed', changed);
    return () => {
      document.removeEventListener('visibilitychange', hidden);
      window.removeEventListener('pagehide', leaving);
      window.removeEventListener('auth-changed', changed);
      clear();
    };
  }, [clear, stop]);
  useEffect(() => {
    stop('Arrival checks are off.');
    setDetected(null);
  }, [trip.chatId, trip.agentChatId, trip.route, stop]);
  useEffect(() => {
    if (blocked)
      stop('Arrival checks stopped. Resolve the unsaved visit update before starting again.');
  }, [blocked, stop]);
  useEffect(() => {
    if (active && !target) stop('No next attraction is available. Arrival checks stopped.');
  }, [active, target, stop]);
  const start = () => {
    if (active || busy || blocked) return;
    if (!window.isSecureContext || !navigator.geolocation?.watchPosition) {
      setMessage(
        'Arrival checks need location support and a secure connection. Manual visits still work.'
      );
      return;
    }
    if (document.visibilityState !== 'visible' || !target) return;
    stop();
    const session = getSession();
    if (!session.owner || !session.accessToken) return;
    const started = generation.current;
    const route = trip.route;
    const chatId = trip.chatId;
    tracker.current = createArrivalTracker();
    setActive(true);
    setMessage('Waiting for location permission and a fresh reading…');
    try {
      const id = navigator.geolocation.watchPosition(
        (position) => {
          if (started !== generation.current) return;
          if (!isCurrentSession(session) || document.visibilityState !== 'visible') {
            stop('Arrival checks stopped. Start again when you return to this trip.');
            return;
          }
          const latest = current.current;
          if (latest.route !== route || latest.chatId !== chatId) {
            stop('Arrival checks stopped because the trip route changed.');
            return;
          }
          if (latest.busy || latest.blocked) {
            tracker.current?.reset();
            return;
          }
          const result = tracker.current?.observe(position, latest.target);
          if (!result) return;
          if (result.state === 'arrived') {
            setDetected({ id: result.id, name: result.name });
            setMessage(`Arrival detected at ${result.name}. Updating your visited stops.`);
            latest.onArrived(result.id);
          } else setMessage(MESSAGES[result.reason]);
        },
        (error) => {
          if (started !== generation.current) return;
          stop(
            error.code === 1
              ? 'Location permission was denied. Arrival checks are off; manual visits still work.'
              : 'Location is unavailable. Arrival checks are off; start again or use manual visits.'
          );
        },
        { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
      );
      if (started === generation.current) watch.current = id;
      else navigator.geolocation.clearWatch(id);
    } catch {
      stop('Location is unavailable. Arrival checks are off; manual visits still work.');
    }
  };
  const canUndo = detected && visitedStopIds(trip.presentation).has(detected.id);
  return (
    <section className="rt-sheet rt-stack" aria-label="Arrival assist">
      <h2 className="rt-title">Arrival assist</h2>
      <p className="rt-caption">
        With your permission, the next attraction is marked visited after you stay nearby briefly.
        Checks run only while this page is visible. The app does not save or share your location.
      </p>
      {target && <p className="rt-caption">Next attraction: {target.name}</p>}
      {!target && (
        <p className="rt-caption">
          No next attraction has matching route coordinates and timing. Use manual visits.
        </p>
      )}
      <p className="rt-caption" role="status">
        {message}
      </p>
      {detected && <p className="rt-caption">Detected arrival: {detected.name}</p>}
      {active ? (
        <ActionButton variant="secondary" onClick={() => stop('Arrival checks stopped.')}>
          Stop arrival checks
        </ActionButton>
      ) : (
        <ActionButton variant="secondary" onClick={start} disabled={busy || blocked || !target}>
          Enable location and mark nearby stops visited
        </ActionButton>
      )}
      {canUndo && (
        <ActionButton
          variant="secondary"
          disabled={busy || blocked}
          onClick={() => {
            stop('Undo requested. Arrival checks stopped.');
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
ArrivalAssist.propTypes = {
  trip: PropTypes.object.isRequired,
  busy: PropTypes.bool,
  blocked: PropTypes.bool,
  onArrived: PropTypes.func.isRequired,
  onUndo: PropTypes.func.isRequired,
};
