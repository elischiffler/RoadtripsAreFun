import { Box, Typography } from '@mui/material';
import PropTypes from 'prop-types';
import '../pages/ItineraryPage/ItineraryPage.css';

export default function ItineraryDays({ itinerary }) {
  return (
    <>
      {itinerary.map((day, index) => (
        <Box key={index} className="day-box">
          <Box className="day-header">
            <Typography variant="h6">{day['date']}</Typography>
          </Box>
          <Box>
            {day['stops'].map((activity, idx) => (
              <Box key={idx} className="activity-box">
                {activity.optional && (
                  <Typography variant="body2" className="activity-time">
                    Optional evening suggestion - choose one
                  </Typography>
                )}
                <Typography variant="body1">
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
                </Typography>
                {activity.time !== 'Unscheduled' && (
                  <Typography variant="body2" className="activity-time">
                    {`${activity.optional ? 'Suggested visit' : activity.kind === 'arrival' || activity.address ? 'Arrival time' : 'Departure time'}: ${activity.time}`}
                    {activity.timezone ? ` (${activity.timezone})` : ''}
                  </Typography>
                )}
                {activity.address && (
                  <Typography variant="body2" className="activity-time">
                    {`Address: ${activity.address}`}
                  </Typography>
                )}
                {activity.price != null && (
                  <Typography variant="body2" className="activity-time">
                    {`${activity.room_offers?.length > 1 ? 'Sum of independent room quotes' : 'Price'}: $${activity.price}`}
                  </Typography>
                )}
                {activity.room_offers?.map((offer, roomIndex) => (
                  <Typography key={roomIndex} variant="body2" className="activity-time">
                    <a href={offer.url} target="_blank" rel="noopener noreferrer">
                      {`Room ${roomIndex + 1}: ${offer.room.adults} adults, ${offer.room.child_ages.length ? `children aged ${offer.room.child_ages.join(', ')}` : 'no children'} — $${offer.price} with taxes and fees`}
                    </a>
                  </Typography>
                ))}
                {activity.room_offers?.length > 1 && (
                  <Typography variant="body2" className="activity-time">
                    Confirm simultaneous room availability with the booking provider.
                  </Typography>
                )}
                {activity.notice && (
                  <Typography variant="body2" className="activity-time">
                    {activity.notice}
                  </Typography>
                )}
                {activity.optional && activity.return_by && (
                  <Typography variant="body2" className="activity-time">
                    {activity.return_time
                      ? `Suggested return: ${activity.return_time}`
                      : `Return to hotel by: ${activity.return_by}`}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>
        </Box>
      ))}
    </>
  );
}

ItineraryDays.propTypes = { itinerary: PropTypes.array.isRequired };
