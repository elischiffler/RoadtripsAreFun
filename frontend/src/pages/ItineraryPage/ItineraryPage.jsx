import ItineraryDays from '../../components/ItineraryDays';
import { Box, Typography, Container } from '@mui/material';
import TripsButton from '../../components/buttons/TripsButton';
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
        <ItineraryDays itinerary={UserChatData.itinerary} />
      </Box>

      {/* Floating nav buttons — bottom-left, beside the saved-trip navigation */}
      <Box className="itinerary-fab-group">
        <MapButton route={UserChatData.route} showRing={false} />
        <TripsButton />
      </Box>
    </Container>
  );
};

export default ItineraryPage;
