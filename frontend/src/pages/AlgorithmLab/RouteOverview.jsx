import PropTypes from 'prop-types';
import Map from '../../components/Map';

export default function RouteOverview({ route }) {
  const geometry = route?.geometry?.coordinates;
  return (
    <div className="lab-route-overview">
      {geometry?.length > 1 ? (
        <div className="lab-map" aria-label="Route map">
          <Map
            UserChatData={{
              route,
              startConfirmed: { longitude: geometry[0][0], latitude: geometry[0][1] },
              endConfirmed: { longitude: geometry.at(-1)[0], latitude: geometry.at(-1)[1] },
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
              <li key={index}>
                <strong>{stop.name}</strong>
                {stop.type && <small>{stop.type.replaceAll('_', ' ')}</small>}
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
