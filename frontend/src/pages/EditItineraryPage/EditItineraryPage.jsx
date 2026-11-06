import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DesignFrame, Sheet, ActionButton } from '../../design';
import Map from '../../components/Map';
import { loadRouteAlternatives } from '../../services/routeAlternatives';
import { getSession, isCurrentSession } from '../../services/session';
import { useStoredTrip } from '../useStoredTrip';
import './EditItineraryPage.css';

const EditItineraryPage = () => {
  const logs = useStoredTrip();
  const trip = logs?.getChatDataById(logs.currentId) || logs?.chatdata?.[0];
  const [ideas, setIdeas] = useState(null);
  const [status, setStatus] = useState('idle');
  const [selectedIdea, setSelectedIdea] = useState(null);
  const controller = useRef(null);
  const mapViewport = useRef(null);
  const requestNumber = useRef(0);
  useEffect(() => {
    controller.current?.abort();
    requestNumber.current += 1;
    setIdeas(null);
    setSelectedIdea(null);
    setStatus('idle');
    return () => {
      controller.current?.abort();
      requestNumber.current += 1;
    };
  }, [trip?.chatId, trip?.route]);
  const loadIdeas = async () => {
    controller.current?.abort();
    controller.current = new AbortController();
    const requestId = ++requestNumber.current;
    const session = getSession();
    setStatus('loading');
    setSelectedIdea(null);
    try {
      const result = await loadRouteAlternatives(trip.route, controller.current.signal);
      if (!isCurrentSession(session) || requestId !== requestNumber.current) return;
      setIdeas(result);
      setStatus('ready');
    } catch {
      if (isCurrentSession(session) && requestId === requestNumber.current) setStatus('error');
    }
  };
  return (
    <DesignFrame className="trip-experience edit-itinerary-page">
      {!trip?.route ? (
        <Sheet>
          <h1 className="rt-display">No Route Available</h1>
          <Link to="/trips">Saved trips</Link>
        </Sheet>
      ) : (
        <>
          <header className="rt-stack">
            <h1 className="rt-display">Edit itinerary</h1>
            <Link to="/trip">Back to trip</Link>
          </header>
          <div
            ref={mapViewport}
            tabIndex={-1}
            className="trip-map-viewport"
            aria-label="Trip route map"
          >
            <Map
              key={trip.chatId}
              UserChatData={trip}
              suggestions={ideas?.places}
              selectedSuggestion={selectedIdea}
              onSelectSuggestion={setSelectedIdea}
            />
          </div>
          <Sheet floating>
            <h2 className="rt-title">Find places along the route</h2>
            <p className="rt-copy">
              Suggestions are not added to your itinerary. Visit availability and driving detours
              need checking.
            </p>
            <ActionButton variant="secondary" disabled={status === 'loading'} onClick={loadIdeas}>
              {status === 'loading'
                ? 'Finding places…'
                : status === 'error'
                  ? 'Retry search'
                  : 'Find places'}
            </ActionButton>
            {status === 'loading' && (
              <p className="rt-caption" role="status">
                Searching along the route…
              </p>
            )}
            {status === 'error' && (
              <p className="rt-caption" role="alert">
                Places could not be loaded. Please retry.
              </p>
            )}
            {ideas && (
              <>
                {ideas.notice && <p className="rt-caption">{ideas.notice}</p>}
                {ideas.coverage && !ideas.coverage.continuous && (
                  <p className="rt-caption">
                    Sampled across the route; gaps between searches may remain.
                  </p>
                )}
                {!ideas.places.length && (
                  <p className="rt-copy" role="status">
                    No places found along this route.
                  </p>
                )}
                <ul className="trip-ideas-list">
                  {ideas.places.map((place) => (
                    <li key={place.id}>
                      <h3 className="rt-title">{place.name}</h3>
                      <ActionButton
                        variant="secondary"
                        aria-label={`View on map: ${place.name}`}
                        onClick={() => {
                          setSelectedIdea(place);
                          mapViewport.current?.scrollIntoView?.({ block: 'nearest' });
                          mapViewport.current?.focus({ preventScroll: true });
                        }}
                      >
                        View on map
                      </ActionButton>
                      {place.address && <p className="rt-copy">{place.address}</p>}
                      {Number.isFinite(place.offset_miles) && (
                        <p className="rt-caption">
                          {place.offset_miles.toFixed(1)} miles from route sample · driving detour
                          unverified
                        </p>
                      )}
                      {place.url && (
                        <a href={place.url} target="_blank" rel="noopener noreferrer">
                          Place information: {place.name}
                        </a>
                      )}
                      <p className="rt-caption">
                        Source: {place.source_attribution || place.source || 'Place catalog'}
                        {place.source_release ? ` · ${place.source_release}` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Sheet>
        </>
      )}
    </DesignFrame>
  );
};
export default EditItineraryPage;
