import { Link } from 'react-router-dom';
import { DesignFrame, Sheet } from '../../design';
import TripExperienceNav from '../../components/TripExperienceNav';
import Map from '../../components/Map';
import { useStoredTrip } from '../useStoredTrip';
import './MapPage.css';

const MapPage = () => {
  const logs = useStoredTrip();
  const trip = logs?.getChatDataById(logs.currentId) || logs?.chatdata?.[0];
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
            <h1 className="rt-display">View map</h1>
            <TripExperienceNav trip={trip} view="map" />
          </header>
          <div className="trip-map-viewport" aria-label="Trip route map">
            <Map key={trip.chatId} UserChatData={trip} />
          </div>
        </>
      )}
    </DesignFrame>
  );
};
export default MapPage;
