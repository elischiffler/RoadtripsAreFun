import { Link } from 'react-router-dom';
import { DesignFrame, Sheet } from '../../design';
import TripExperienceNav from '../../components/TripExperienceNav';
import TripVisitProgress from '../../components/TripVisitProgress';
import { useStoredTrip } from '../useStoredTrip';
import './ItineraryPage.css';

const ItineraryPage = () => {
  const logs = useStoredTrip();
  const trip = logs?.getChatDataById(logs.currentId) || logs?.chatdata?.[0];
  return (
    <DesignFrame className="trip-experience itinerary-page">
      {!trip?.itinerary?.length ? (
        <Sheet>
          <h1 className="rt-display">No Itinerary Available</h1>
          <Link to="/trips">Saved trips</Link>
        </Sheet>
      ) : (
        <>
          <header className="rt-stack">
            <p className="rt-caption">Your road trip</p>
            <h1 className="rt-display">A day at a time</h1>
            <TripExperienceNav trip={trip} view="itinerary" />
          </header>
          <TripVisitProgress key={trip.chatId} trip={trip} />
        </>
      )}
    </DesignFrame>
  );
};
export default ItineraryPage;
