import { React, useContext } from "react";
import { Box } from "@mui/material";
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
  const UserChatData = ChatLogsData?.chatdata?.[ChatLogsData.currentId - 1];
  console.log(UserChatData);

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
