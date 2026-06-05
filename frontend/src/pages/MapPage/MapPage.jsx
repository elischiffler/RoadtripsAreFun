import { useContext, useEffect } from 'react';
import { Box, Typography } from '@mui/material';
import ItineraryButton from '../../components/buttons/ItineraryButton';
import ChatButton from '../../components/buttons/ChatButton';
import Map from '../../components/Map';
import { UserDataContext } from '../../states/UserDataContext';
import './MapPage.css';

const MapPage = () => {
  // Lock body scroll while on this page
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  // Retrieve the the instance of UserData from sessionStorage
  const { UserData } = useContext(UserDataContext);

  // Grab the chat logs
  const ChatLogsData = UserData?.chatlogs || {};
  const UserChatData =
    ChatLogsData?.chatdata?.length > 0
      ? ChatLogsData.getChatDataById(ChatLogsData.currentId) || ChatLogsData.chatdata[0]
      : null;

  if (!UserChatData || !UserChatData.route) {
    return (
      <Box className="map-page-container">
        <Box
          className="map-empty"
          sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}
        >
          <Typography variant="h6">No Route Available</Typography>
        </Box>
        {/* Floating bottom buttons even on empty state */}
        <Box className="map-overlay-buttons">
          <ChatButton />
        </Box>
      </Box>
    );
  }

  return (
    <Box className="map-page-container">
      {/* Full-bleed map */}
      <Map UserChatData={UserChatData} />

      {/* Floating bottom-right button cluster */}
      <Box className="map-overlay-buttons">
        <ItineraryButton itinerary={UserChatData.itinerary} showRing={false} />
        <ChatButton />
      </Box>
    </Box>
  );
};

export default MapPage;
