import { useContext, useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { UserDataContext, Data } from '../states/UserDataContext';
import { getSession, isCurrentSession } from '../services/session';
import { updateUserData } from '../services/savedTrips';
import { itineraryEntries, toggleVisited, visitedStopIds } from '../services/tripPresentation';
import ItineraryDays from './ItineraryDays';
import { ActionButton } from '../design';

// Account-owned context instance, so unsaved feedback survives switching trip views.
const saveStates = new WeakMap();
export default function TripVisitProgress({ trip }) {
  const { UserData, setUserData, chats } = useContext(UserDataContext);
  const logs = UserData.chatlogs;
  if (!saveStates.has(logs)) saveStates.set(logs, new Map());
  const states = saveStates.get(logs);
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
    if (states.get(trip.chatId) === 'saving') return;
    const session = getSession();
    states.set(trip.chatId, 'saving');
    setStatus('saving');
    let saved = false;
    try {
      saved = Boolean(
        session.accessToken && (await updateUserData(session.accessToken, snapshot, chats, logs))
      );
    } catch {
      /* Keep the local presentation and offer retry. */
    }
    if (!isCurrentSession(session)) return;
    const nextStatus = saved ? 'saved' : 'error';
    states.set(trip.chatId, nextStatus);
    window.dispatchEvent(new Event('trip-visits-changed'));
    if (mounted.current) setStatus(nextStatus);
  };
  const toggle = (id) => {
    if (states.get(trip.chatId) === 'saving') return;
    const snapshot = { ...trip, presentation: toggleVisited(trip.presentation, id) };
    logs.chatdata = logs.chatdata.map((item) => (item.chatId === trip.chatId ? snapshot : item));
    setUserData((current) => (current.chatlogs === logs ? new Data(logs) : current));
    void save(snapshot);
  };
  return (
    <>
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
              : status === 'error'
                ? 'Visit updates are kept here, but could not be saved. Retry before leaving or refreshing.'
                : 'Mark each stop when you visit. Your schedule does not mark it for you.'}
        </p>
        {status === 'error' && (
          <ActionButton variant="secondary" onClick={() => void save(trip)}>
            Retry saving visits
          </ActionButton>
        )}
      </section>
      <ItineraryDays
        itinerary={trip.itinerary}
        presentation={trip.presentation}
        onToggleVisited={toggle}
        saving={status === 'saving'}
      />
    </>
  );
}
TripVisitProgress.propTypes = { trip: PropTypes.object.isRequired };
