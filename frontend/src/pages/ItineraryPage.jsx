import React from "react";
import {
  Box,
  CssBaseline,
  Typography,
  ThemeProvider,
  Container,
} from "@mui/material";
import customTheme from "../components/Theme";
import LogoButton from "../components/LogoButton";
import ChatButton from "../components/ChatButton";
import MapButton from "../components/MapButton";

const ItineraryPage = () => {
  // Sample itinerary data
  const itinerary = [
    {
      day: "June 19th",
      activities: [
        "Visit the local museum",
        "Lunch at the downtown cafe",
        "Explore the historic district",
      ],
    },
    {
      day: "June 20th",
      activities: [
        "Hiking in the national park",
        "Picnic at the lake",
        "Stargazing at the observatory",
      ],
    },
    {
      day: "June 21st",
      activities: [
        "Morning yoga on the beach",
        "Brunch at the seaside restaurant",
        "Relax at the spa",
      ],
    },
  ];

  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Container
        maxWidth={false}
        disableGutters
        sx={{
          width: "100vw",
          height: "100vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Fixed Top Box */}
        <Box
          sx={{
            position: "fixed",
            top: 0,
            width: "100%",
            height: "7%",
            bgcolor: "primary.main", // Dark Blue
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingX: 2,
            zIndex: 1000,
          }}
        >
          <LogoButton />
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h6" color="white" align="center">
              Trip Itinerary
            </Typography>
          </Box>
        </Box>

        {/* Scrollable Main Content Box */}
        <Box
          sx={{
            flex: 1,
            bgcolor: "primary.main", // Light Blue
            color: "#003366", // Dark Blue text
            padding: 3,
            display: "flex",
            flexDirection: "column",
            gap: 3,
            position: "relative",
            marginTop: "3.9%", // Space for fixed top
            marginBottom: "3.9%", // Space for fixed bottom
            overflowY: "auto",
            "&::-webkit-scrollbar": {
              width: "12px",
            },
            "&::-webkit-scrollbar-track": {
              background: "primary.main", // Use main background color
            },
            "&::-webkit-scrollbar-thumb": {
              background: "#003366",
              borderRadius: "10px",
            },
            "&::-webkit-scrollbar-thumb:hover": {
              background: "#002244",
            },
          }}
        >
          {itinerary.map((day, index) => (
            <Box
              key={index}
              sx={{
                bgcolor: "white",
                borderRadius: 2,
                padding: 2,
                boxShadow: 2,
              }}
            >
              <Box
                sx={{
                  bgcolor: "#663399", // Purple
                  color: "white",
                  borderRadius: 2,
                  padding: 1,
                  mb: 2,
                }}
              >
                <Typography variant="h6" sx={{ fontWeight: "bold" }}>
                  {day.day}
                </Typography>
              </Box>
              <Box sx={{ mt: 1 }}>
                {day.activities.map((activity, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      bgcolor: "rgba(255, 192, 203, 0.6)", // Pink with 60% opacity
                      borderRadius: 2,
                      padding: 1,
                      mb: 1,
                      boxShadow: 1,
                    }}
                  >
                    <Typography variant="body1">{activity}</Typography>
                    <Typography variant="body2" sx={{ color: "#555" }}>
                      {idx === 0
                        ? "9:00 AM"
                        : idx === 1
                        ? "12:00 PM"
                        : "3:00 PM"}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          ))}
        </Box>

        {/* Fixed Bottom Button Container */}
        <Box
          sx={{
            position: "fixed",
            bottom: 0,
            width: "100%",
            height: "7%",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: 2,
            boxSizing: "border-box",
            backgroundColor: "primary.main", // Dark Blue
            zIndex: 1000,
          }}
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              width: "auto",
              height: "100%",
              mb: 1.8,
            }}
          >
            <ChatButton />
          </Box>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              width: "auto",
              height: "100%",
              mb: 1.8,
            }}
          >
            <MapButton />
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
};

export default ItineraryPage;
