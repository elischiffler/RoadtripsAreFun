import { React, useEffect } from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ItineraryButton from "../../components/ItineraryButton";
import ChatButton from "../../components/ChatButton";
import Map from "../../components/Map";
import "./MapPage.css";

const MapPage = () => {
  //Import colors
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--white-main", customTheme.palette.white.main);
    root.style.setProperty("--white-light", customTheme.palette.white.light);
    root.style.setProperty("--white-dark", customTheme.palette.white.dark);
    root.style.setProperty("--white-black", customTheme.palette.white.black);
    root.style.setProperty("--green-main", customTheme.palette.green.main);
  }, []);

  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
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
    </ThemeProvider>
  );
};

export default MapPage;
