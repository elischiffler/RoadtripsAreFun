import { React } from "react";
import { Box } from "@mui/material";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/buttons/ItineraryButton";
import ChatButton from "../../components/buttons/ChatButton";
import Map from "../../components/Map";
import "./MapPage.css";

const MapPage = () => {

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
          <ItineraryButton />
        </Box>

        {/* Chat Button */}
        <Box className="chat-button-container">
          <ChatButton />
        </Box>
      </Box>

      {/* Main Content */}
      <Box className="main-content">
        <Map />
      </Box>
    </Box>
  );
};

export default MapPage;
