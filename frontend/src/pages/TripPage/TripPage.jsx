import { Link } from 'react-router-dom';
import { DesignFrame, Sheet } from '../../design';
import Map from '../../components/Map';
import ShareTripPanel from '../../components/ShareTripPanel';
import TripExperienceNav from '../../components/TripExperienceNav';
import TripVisitProgress from '../../components/TripVisitProgress';
import { useStoredTrip } from '../useStoredTrip';
import './TripPage.css';

export default function TripPage() {
  const logs = useStoredTrip();
  const trip = logs?.getChatDataById(logs.currentId) || logs?.chatdata?.[0];
  const route = trip?.route;
  const days = trip?.itinerary || [];
  const coordinates = (route?.geometry?.coordinates || []).filter(
    (point) => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite)
  );
  const west = Math.min(...coordinates.map((point) => point[0]));
  const east = Math.max(...coordinates.map((point) => point[0]));
  const south = Math.min(...coordinates.map((point) => point[1]));
  const north = Math.max(...coordinates.map((point) => point[1]));
  const points = coordinates
    .map(
      ([lon, lat]) =>
        `${20 + ((lon - west) / (east - west || 1)) * 360},${180 - ((lat - south) / (north - south || 1)) * 160}`
    )
    .join(' ');
  const departure = trip?.tripProfile?.start_date;
  const livePreview =
    import.meta.env.VITE_LOCAL_JOURNEY !== 'true' &&
    Boolean(import.meta.env.VITE_MAPBOX_TOKEN) &&
    trip?.startConfirmed &&
    trip?.endConfirmed &&
    coordinates.length > 1;
  const dates = days.length
    ? [days[0].date, days.at(-1).date]
        .filter((value, index, list) => value && list.indexOf(value) === index)
        .join(' – ')
    : departure;

  return (
    <DesignFrame className="trip-experience trip-page">
      {!trip ? (
        <Sheet>
          <h1 className="rt-display">No trip selected</h1>
          <Link to="/trips">Saved trips</Link>
        </Sheet>
      ) : (
        <>
          <header className="rt-stack">
            <h1 className="rt-display">Trip details</h1>
            <TripExperienceNav trip={trip} view="trip" />
          </header>
          <Sheet>
            <dl className="trip-facts">
              {trip.startConfirmed?.address && (
                <div>
                  <dt>From</dt>
                  <dd>{trip.startConfirmed.address}</dd>
                </div>
              )}
              {trip.endConfirmed?.address && (
                <div>
                  <dt>To</dt>
                  <dd>{trip.endConfirmed.address}</dd>
                </div>
              )}
              {dates && (
                <div>
                  <dt>Dates</dt>
                  <dd>{dates}</dd>
                </div>
              )}
              {Number.isFinite(route?.duration) && (
                <div>
                  <dt>Driving</dt>
                  <dd>
                    {Math.floor(Math.round(route.duration / 60) / 60)}h{' '}
                    {Math.round(route.duration / 60) % 60}m
                  </dd>
                </div>
              )}
              {Number.isFinite(route?.distance) && (
                <div>
                  <dt>Distance</dt>
                  <dd>{Math.round(route.distance / 1609.344).toLocaleString()} miles</dd>
                </div>
              )}
            </dl>
            {route ? (
              <div className="trip-map-preview">
                {livePreview && <Map preview UserChatData={trip} />}
                <Link className="trip-map-preview-link" to="/map" aria-label="View map">
                  {!livePreview &&
                    (points ? (
                      <svg viewBox="0 0 400 200" role="img" aria-label="Route preview">
                        <polyline
                          points={points}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : (
                      <span>Route map</span>
                    ))}
                  <span className="trip-map-preview-label">View map</span>
                </Link>
              </div>
            ) : (
              <p className="rt-copy">No route available.</p>
            )}
          </Sheet>
          <ShareTripPanel key={`${trip.chatId}:${trip.agentChatId}`} trip={trip} />
          <section className="rt-stack" aria-labelledby="trip-itinerary-title">
            <div className="trip-itinerary-heading">
              <h2 id="trip-itinerary-title" className="rt-title">
                Itinerary
              </h2>
              {route && <Link to="/itinerary/edit">Edit itinerary</Link>}
            </div>
            {days.length ? (
              <div
                className="trip-itinerary-scroll"
                tabIndex={0}
                role="region"
                aria-label="Trip itinerary"
              >
                <TripVisitProgress key={trip.chatId} trip={trip} />
              </div>
            ) : (
              <p className="rt-copy">No itinerary available.</p>
            )}
          </section>
        </>
      )}
    </DesignFrame>
  );
}
