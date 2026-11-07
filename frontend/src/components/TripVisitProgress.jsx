import { useContext, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { UserDataContext, Data } from '../states/UserDataContext';
import { getSession, isCurrentSession } from '../services/session';
import { updateUserData } from '../services/savedTrips';
import { itineraryEntries, visitedStopIds } from '../services/tripPresentation';
import ItineraryDays from './ItineraryDays';
import TripArrivalTracking from './TripArrivalTracking';
import { correctArrival, recordArrival } from '../services/tripArrivals';
import { ActionButton } from '../design';

// Account-owned context instance, so unsaved feedback survives switching trip views.
const saveStates = new WeakMap();
export default function TripVisitProgress({ trip }) {
  const { UserData, setUserData, chats } = useContext(UserDataContext);
  const logs = UserData.chatlogs;
  if (!saveStates.has(logs)) saveStates.set(logs, new Map());
  const states = saveStates.get(logs);
  const [correcting, setCorrecting] = useState(false);
  const [status, setStatus] = useState(states.get(trip.chatId) || 'idle');
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    const refresh = () => setStatus(states.get(trip.chatId) || 'idle');
    refresh();
    window.addEventListener('trip-visits-changed', refresh);
    return () => window.removeEventListener('trip-visits-changed', refresh);
  }, [states, trip.chatId]);
  const visited = visitedStopIds(trip.presentation);
  const ids = itineraryEntries(trip.itinerary).flatMap((day) => day.stops.map((item) => item.id));
  const count = ids.filter((id) => visited.has(id)).length;
  const save = async (snapshot) => {
    if (['saving', 'conflict'].includes(states.get(trip.chatId))) return;
    const session = getSession();
    states.set(trip.chatId, 'saving');
    setStatus('saving');
    let saved = false;
    try {
      saved = Boolean(
        session.accessToken &&
          (await updateUserData(session.accessToken, snapshot, chats, logs, {
            presentationOnly: true,
          }))
      );
    } catch {
      /* Keep the local presentation and offer retry. */
    }
    if (!isCurrentSession(session)) return;
    const nextStatus = saved ? 'saved' : snapshot.saveConflict ? 'conflict' : 'error';
    states.set(trip.chatId, nextStatus);
    window.dispatchEvent(new Event('trip-visits-changed'));
    if (mounted.current) setStatus(nextStatus);
  };
  const canRecord = () => !['saving', 'conflict', 'error'].includes(states.get(trip.chatId));
  const update = (presentation) => {
    if (!canRecord()) return;
    const snapshot = { ...trip, presentation };
    logs.chatdata = logs.chatdata.map((item) => (item.chatId === trip.chatId ? snapshot : item));
    setUserData((current) => (current.chatlogs === logs ? new Data(logs) : current));
    void save(snapshot);
  };
  const toggle = (id) => update(correctArrival(trip.presentation, trip.chatId, id));
  const arrive = (event) => {
    if (!visited.has(event.stopId)) update(recordArrival(trip.presentation, event));
  };
  return (
    <>
      <TripArrivalTracking
        trip={trip}
        onArrival={arrive}
        canRecord={canRecord}
        blocked={status === 'error' || status === 'conflict'}
      />
      <section className="trip-visit-summary" aria-label="Trip visit progress">
        <p className="rt-title">
          {count} of {ids.length} stops visited
        </p>
        <progress max={ids.length || 1} value={count} aria-label="Stops visited" />
        <p className="rt-caption" role="status">
          {status === 'saving'
            ? 'Saving visit updates…'
            : status === 'saved'
              ? 'Visit updates saved.'
              : status === 'conflict'
                ? 'This saved trip changed. Open Saved trips and reload it before marking more visits.'
                : status === 'error'
                  ? 'Visit updates are kept here, but could not be saved. Retry before leaving or refreshing.'
                  : 'Arrivals are detected only when enabled. Your schedule does not mark stops for you.'}
        </p>
        {status === 'error' && (
          <ActionButton variant="secondary" onClick={() => void save(trip)}>
            Retry saving visits
          </ActionButton>
        )}
        <ActionButton
          variant="secondary"
          onClick={() => setCorrecting((value) => !value)}
          aria-expanded={correcting}
        >
          {correcting ? 'Done correcting arrivals' : 'Correct an arrival'}
        </ActionButton>
        {correcting && (
          <p className="rt-caption">
            Mark a missed arrival or undo one below. Undo turns off automatic detection for that
            stop until you mark it again.
          </p>
        )}
      </section>
      <ItineraryDays
        itinerary={trip.itinerary}
        presentation={trip.presentation}
        onToggleVisited={correcting ? toggle : undefined}
        saving={!canRecord()}
      />
    </>
  );
}
TripVisitProgress.propTypes = { trip: PropTypes.object.isRequired };
