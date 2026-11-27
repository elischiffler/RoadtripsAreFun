import PlaceTiming from '../../components/PlaceTiming.jsx';
import PropTypes from 'prop-types';
import Map from '../../components/Map';
import { isAppleRoute } from '../../services/directionsCapability';

export default function RouteOverview({ route }) {
  const geometry = route?.geometry?.coordinates;
  const endpoints =
    geometry?.length > 1 ? geometry : route.coordinates?.map(([lat, lon]) => [lon, lat]);
  return (
    <div className="lab-route-overview">
      {(geometry?.length > 1 || isAppleRoute(route)) && endpoints?.length > 1 ? (
        <div className="lab-map" aria-label="Route map">
          <Map
            studio
            UserChatData={{
              route,
              startConfirmed: { longitude: endpoints[0][0], latitude: endpoints[0][1] },
              endConfirmed: { longitude: endpoints.at(-1)[0], latitude: endpoints.at(-1)[1] },
            }}
          />
        </div>
      ) : (
        <p className="lab-note">Map geometry is unavailable for this run.</p>
      )}
      <div>
        <h3>Along the way</h3>
        {route.stops?.length ? (
          <ol className="lab-route-stops">
            {route.stops.map((stop, index) => (
              <li key={index} data-type={stop.type}>
                <span
                  className="lab-stop-dot"
                  aria-label={stop.type === 'hotel' ? 'Overnight stay' : 'Place'}
                >
                  {index + 1}
                </span>
                <div>
                  <strong>{stop.name}</strong>
                  <PlaceTiming place={stop} />
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p>No stops recorded for this route.</p>
        )}
      </div>
    </div>
  );
}
RouteOverview.propTypes = { route: PropTypes.object.isRequired };
