import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';
import './TripExperience.css';

export default function TripExperienceNav({ trip, view }) {
  const select = () => sessionStorage.setItem('selectedChatId', String(trip.chatId));
  return (
    <nav className="trip-view-nav" aria-label="Trip views">
      <Link to="/trip" onClick={select} aria-current={view === 'trip' ? 'page' : undefined}>
        Trip
      </Link>
      <Link
        to="/itinerary"
        onClick={select}
        aria-current={view === 'itinerary' ? 'page' : undefined}
      >
        Itinerary
      </Link>
      <Link to="/map" onClick={select} aria-current={view === 'map' ? 'page' : undefined}>
        View map
      </Link>
      <Link
        to="/itinerary/edit"
        onClick={select}
        aria-current={view === 'edit' ? 'page' : undefined}
      >
        Edit itinerary
      </Link>
    </nav>
  );
}
TripExperienceNav.propTypes = {
  trip: PropTypes.object.isRequired,
  view: PropTypes.oneOf(['trip', 'itinerary', 'map', 'edit']).isRequired,
};
