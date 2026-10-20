import PropTypes from 'prop-types';
import { localTimestamp } from './placeTiming';

export default function PlaceTiming({ place }) {
  const arrival = localTimestamp(place.arrival_time, place.timezone);
  const leaving = localTimestamp(place.departure_time, place.timezone);
  if (!arrival && !leaving) return null;
  return (
    <div className="place-timing" aria-label="Place timing">
      <small style={{ display: 'block' }}>Arrival: {arrival ?? 'Unavailable'}</small>
      {place.type !== 'end' && (
        <small style={{ display: 'block' }}>Leaving: {leaving ?? 'Unavailable'}</small>
      )}
    </div>
  );
}
PlaceTiming.propTypes = { place: PropTypes.object.isRequired };
