import React from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/ItineraryButton";
import ChatButton from "../../components/ChatButton";
import Map from "../../components/Map";
import "./MapPage.css"; // Import the CSS file

const MapPage = () => {
  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Box
       className="map-page-container"
       sx={{
        "--pink-main": customTheme.palette.pink.main,
        "--purple-main": customTheme.palette.purple.main,
      }}>
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
    </ThemeProvider>
  );
};

export default MapPage;