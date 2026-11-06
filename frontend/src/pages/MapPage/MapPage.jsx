import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DesignFrame, Sheet, ActionButton } from '../../design';
import TripExperienceNav from '../../components/TripExperienceNav';
import Map from '../../components/Map';
import { loadRouteAlternatives } from '../../services/routeAlternatives';
import { getSession, isCurrentSession } from '../../services/session';
import { useStoredTrip } from '../useStoredTrip';
import './MapPage.css';

const MapPage = () => {
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
    <DesignFrame className="trip-experience map-page">
      {!trip?.route ? (
        <Sheet>
          <h1 className="rt-display">No Route Available</h1>
          <Link to="/trips">Saved trips</Link>
        </Sheet>
      ) : (
        <>
          <header className="rt-stack">
            <p className="rt-caption">Your road trip</p>
            <h1 className="rt-display">Follow your route</h1>
            <TripExperienceNav trip={trip} view="map" />
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
            <h2 className="rt-title">A little room to explore</h2>
            <p className="rt-copy">
              Browse nearby ideas along your route. These are unscheduled suggestions; opening
              hours, availability and detour timing still need checking.
            </p>
            <ActionButton variant="secondary" disabled={status === 'loading'} onClick={loadIdeas}>
              {status === 'loading'
                ? 'Finding nearby ideas…'
                : status === 'error'
                  ? 'Retry nearby ideas'
                  : 'Find nearby ideas'}
            </ActionButton>
            {status === 'loading' && (
              <p className="rt-caption" role="status">
                Looking around this route…
              </p>
            )}
            {status === 'error' && (
              <p className="rt-caption" role="alert">
                Nearby ideas could not be loaded. Your planned route is still here. Please retry.
              </p>
            )}
            {ideas && (
              <>
                {ideas.notice && <p className="rt-caption">{ideas.notice}</p>}
                {!ideas.places.length && (
                  <p className="rt-copy" role="status">
                    No nearby ideas were found for this route.
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
                          mapViewport.current?.scrollIntoView({ block: 'nearest' });
                          mapViewport.current?.focus({ preventScroll: true });
                        }}
                      >
                        View on map
                      </ActionButton>
                      {place.address && <p className="rt-copy">{place.address}</p>}
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
export default MapPage;
