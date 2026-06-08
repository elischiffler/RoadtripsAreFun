import { useContext } from 'react';
import { Box, Typography, Container } from '@mui/material';
import ChatButton from '../../components/buttons/ChatButton';
import MapButton from '../../components/buttons/MapButton';
import { UserDataContext } from '../../states/UserDataContext';
import './ItineraryPage.css';

const ItineraryPage = () => {
  // Retrieve the global instance of UserData
  const { UserData } = useContext(UserDataContext);
  // Grab the chat logs and make sure everything is defined
  const ChatLogsData = UserData?.chatlogs || {};
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
              {day['stops'].map((activity, idx) =>
                activity['address'] ? (
                  <Box key={idx} className="activity-box">
                    <Typography variant="body1">
                      {activity['url'] ? ( // Conditionally render the name
                        // Makes the name clickable and navigates you to the booking link in a new tab
                        <a
                          href={activity['url']}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="activity-link"
                        >
                          {activity['name']}
                        </a>
                      ) : (
                        activity['name']
                      )}
                    </Typography>
                    <Typography variant="body2" className="activity-time">
                      {`Arrival time: ${activity['time']}`}
                    </Typography>
                    <Typography variant="body2" className="activity-time">
                      {`Address: ${activity['address']}`}
                    </Typography>
                    <Typography variant="body2" className="activity-time">
                      {activity['price'] ? `Price: $${activity['price']}` : null}
                    </Typography>
                  </Box>
                ) : (
                  <Box key={idx} className="activity-box">
                    <Typography variant="body1">{activity['name']}</Typography>
                    <Typography variant="body2" className="activity-time">
                      {`Departure time: ${activity['time']}`}
                    </Typography>
                  </Box>
                )
              )}
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
