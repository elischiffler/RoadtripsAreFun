import PlaceTiming from './PlaceTiming.jsx';
import { compactTimestamp } from './placeTiming';
import './TripExperience.css';
import { itineraryEntries, visitedStopIds } from '../services/tripPresentation';
import { ActionButton } from '../design';
import PropTypes from 'prop-types';
import '../pages/ItineraryPage/ItineraryPage.css';

export default function ItineraryDays({
  itinerary,
  presentation,
  onToggleVisited,
  saving = false,
}) {
  const visited = visitedStopIds(presentation);
  return (
    <div className="rt-design trip-itinerary-days">
      {itineraryEntries(itinerary).map(({ day, stops, meals }, index) => (
        <section key={`${day.date}-${index}`} className="trip-day rt-sheet">
          <header className="day-header">
            <h2 className="rt-title">{day.date}</h2>
          </header>
          <ol className="trip-timeline">
            {stops.map(({ stop: activity, id }) => (
              <li key={id} className="activity-box" data-visited={visited.has(id)}>
                <span className="trip-stop-marker" aria-hidden="true">
                  {visited.has(id) ? '✓' : ''}
                </span>
                {activity.optional && (
                  <p className="activity-time">Optional evening suggestion - choose one</p>
                )}
                <h3 className="trip-stop-title">
                  {activity.url ? (
                    <a
                      href={activity.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="activity-link"
                    >
                      {activity.name}
                    </a>
                  ) : (
                    activity.name
                  )}
                </h3>
                <PlaceTiming place={activity} />
                {!activity.arrival_time &&
                  !activity.departure_time &&
                  activity.time !== 'Unscheduled' && (
                    <p className="activity-time">
                      {`${activity.optional ? 'Suggested visit' : activity.kind === 'arrival' || activity.address ? 'Arrival time' : 'Departure time'}: ${activity.time}`}
                      {activity.timezone ? ` (${activity.timezone})` : ''}
                    </p>
                  )}
                {activity.address && (
                  <p className="activity-time">{`Address: ${activity.address}`}</p>
                )}
                {activity.price != null && (
                  <p className="activity-time">
                    {`${activity.room_offers?.length > 1 ? 'Sum of independent room quotes' : 'Price'}: $${activity.price}`}
                  </p>
                )}
                {activity.room_offers?.map((offer, roomIndex) => (
                  <p key={roomIndex} className="activity-time">
                    <a href={offer.url} target="_blank" rel="noopener noreferrer">
                      {`Room ${roomIndex + 1}: ${offer.room.adults} adults, ${offer.room.child_ages.length ? `children aged ${offer.room.child_ages.join(', ')}` : 'no children'} — $${offer.price} with taxes and fees`}
                    </a>
                  </p>
                ))}
                {activity.room_offers?.length > 1 && (
                  <p className="activity-time">
                    Confirm simultaneous room availability with the booking provider.
                  </p>
                )}
                {activity.notice && <p className="activity-time">{activity.notice}</p>}
                {activity.optional && activity.return_by && (
                  <p className="activity-time">
                    {activity.return_time
                      ? `Suggested return: ${activity.return_time}`
                      : `Return to hotel by: ${activity.return_by}`}
                  </p>
                )}
                {onToggleVisited && (
                  <ActionButton
                    variant="secondary"
                    disabled={saving}
                    onClick={() => onToggleVisited(id)}
                    aria-label={`${visited.has(id) ? 'Undo visited' : 'Mark visited'}: ${activity.name}`}
                  >
                    {visited.has(id) ? 'Undo visited' : 'Mark visited'}
                  </ActionButton>
                )}
              </li>
            ))}
          </ol>
          {meals.length > 0 && (
            <section className="trip-meal-windows" aria-label="Open meal windows">
              <h3 className="rt-title">Open meal windows</h3>
              <ul>
                {meals.map((meal, mealIndex) => (
                  <li key={meal.id || mealIndex}>
                    <h4 className="rt-copy">{meal.name}</h4>
                    <p className="rt-caption">
                      <time dateTime={meal.window_start}>
                        {compactTimestamp(meal.window_start, meal.timezone)?.time ||
                          meal.window_start?.slice(11, 16) ||
                          'Time to choose'}
                      </time>
                      {' – '}
                      <time dateTime={meal.window_end}>
                        {compactTimestamp(meal.window_end, meal.timezone)?.time ||
                          meal.window_end?.slice(11, 16) ||
                          'Time to choose'}
                      </time>
                      {meal.timezone ? ` (${meal.timezone})` : ''}
                    </p>
                    <p className="rt-caption">
                      {meal.notice ||
                        'Open planning window; no time or place is reserved. May overlap driving or visits; adjust the time.'}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </section>
      ))}
    </div>
  );
}

ItineraryDays.propTypes = {
  itinerary: PropTypes.array.isRequired,
  presentation: PropTypes.object,
  onToggleVisited: PropTypes.func,
  saving: PropTypes.bool,
};
