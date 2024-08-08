import React from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";
import customTheme from "../components/Theme";
import LogoButton from "../components/LogoButton";
import ItineraryButton from "../components/ItineraryButton";
import ChatButton from "../components/ChatButton";
import Map from "../components/Map";

const MapPage = () => {
  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Box
        sx={{
          display: "flex",
          height: "100vh",
          overflow: "hidden",
          boxSizing: "border-box",
        }}
      >
        {/* Left Sidebar */}
        <Box
          sx={{
            width: "17%",
            bgcolor: "pink.main",
            display: "flex",
            flexDirection: "column",
            padding: 2,
            boxShadow: 1,
            borderRight: `2px solid ${customTheme.palette.purple.main}`,
            boxSizing: "border-box",
            position: "relative",
            alignItems: "center", // Center align the items
          }}
        >
          {/* Logo Button */}
          <Box
            sx={{
              mb: "auto",
            }}
          >
            <LogoButton />
          </Box>

          {/* Itinerary Button */}
          <Box
            sx={{
              mb: -1,
              width: "100%", // Ensure buttons take full width
            }}
          >
            <ItineraryButton />
          </Box>

          {/* Chat Button */}
          <Box
            sx={{
              width: "100%", // Ensure buttons take full width
            }}
          >
            <ChatButton />
          </Box>
        </Box>

        {/* Main Content */}
        <Box
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            boxSizing: "border-box",
          }}
        >
          <Map />
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default MapPage;
