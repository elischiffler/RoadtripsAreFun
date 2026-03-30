import { React, useContext } from "react";
import { Box, Typography } from "@mui/material";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import ChatButton from "../../components/buttons/ChatButton";
import Map from "../../components/Map";
import { UserDataContext } from "../../states/UserDataContext"
import "./MapPage.css";

const MapPage = () => {

  // Retrieve the the instance of UserData from sessionStorage
  const { UserData } = useContext(UserDataContext);
  
  // Grab the chat logs
  const ChatLogsData = UserData?.chatlogs || {};
  const UserChatData = ChatLogsData?.chatdata?.length > 0
    ? (ChatLogsData.getChatDataById(ChatLogsData.currentId) || ChatLogsData.chatdata[0])
    : null;
  console.log(UserChatData);

  if (!UserChatData || !UserChatData.route) {
    return (
      <Box className="map-page-container">
        <Box className="left-sidebar">
          <Box className="logo-button-container">
            <LogoButton />
          </Box>
          <Box className="chat-button-container">
            <ChatButton />
          </Box>
        </Box>
        <Box className="main-content" sx={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
          <Typography variant="h6">No Route Available</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box className="map-page-container">
      {/* Left Sidebar */}
      <Box className="left-sidebar">
        {/* Logo Button */}
        <Box className="logo-button-container">
          <LogoButton />
        </Box>

        {/* Itinerary Button */}
        <Box className="itinerary-button-container">
          <ItineraryButton itinerary={UserChatData.itinerary}/>
        </Box>

        {/* Chat Button */}
        <Box className="chat-button-container">
          <ChatButton />
        </Box>
      </Box>

      {/* Main Content */}
      <Box className="main-content">
        <Map UserChatData = { UserChatData } />
      </Box>
    </Box>
  );
};

export default MapPage;
