import { Box, Typography, Container } from '@mui/material';
import ChatButton from '../../components/buttons/ChatButton';
import MapButton from '../../components/buttons/MapButton';
import { useStoredTrip } from '../useStoredTrip';
import './ItineraryPage.css';

const ItineraryPage = () => {
  // Retrieve the global instance of UserData
  const ChatLogsData = useStoredTrip();
  const UserChatData =
    ChatLogsData?.chatdata?.length > 0
      ? ChatLogsData.getChatDataById(ChatLogsData.currentId) || ChatLogsData.chatdata[0]
      : null;

  if (!UserChatData || !UserChatData.itinerary) {
    return (
      <Container className="itinerary-page" maxWidth={false} disableGutters>
        <Box className="no-itinerary-message">
          <Typography variant="h6" color="white.black">
            No Itinerary Available
          </Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container className="itinerary-page" maxWidth={false} disableGutters>
      {/* Scrollable Main Content Box */}
      <Box className="scrollable-main-content">
        {UserChatData.itinerary.map((day, index) => (
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
                      {`Price: $${activity.price}`}
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
      </Box>

      {/* Floating nav buttons — bottom-left, same position as chat page */}
      <Box className="itinerary-fab-group">
        <MapButton route={UserChatData.route} showRing={false} />
        <ChatButton />
      </Box>
    </Container>
  );
};

export default ItineraryPage;
