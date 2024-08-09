import { React, useEffect } from "react";
import {
  Box,
  CssBaseline,
  Typography,
  ThemeProvider,
  Container,
} from "@mui/material";
import customTheme from "../../components/Theme";
import LogoButton from "../../components/LogoButton";
import ChatButton from "../../components/ChatButton";
import MapButton from "../../components/MapButton";
import "./ItineraryPage.css";

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
      <Container className="itinerary-page" maxWidth={false} disableGutters>
        {/* Fixed Top Box */}
        <Box className="fixed-top-box">
          <LogoButton />
          <Box className="title">
            <Typography variant="h6" color="white.black">
              Trip Itinerary
            </Typography>
          </Box>
        </Box>

        {/* Scrollable Main Content Box */}
        <Box className="scrollable-main-content">
          {itinerary.map((day, index) => (
            <Box key={index} className="day-box">
              <Box className="day-header">
                <Typography variant="h6">{day.day}</Typography>
              </Box>
              <Box>
                {day.activities.map((activity, idx) => (
                  <Box key={idx} className="activity-box">
                    <Typography variant="body1">{activity}</Typography>
                    <Typography variant="body2" className="activity-time">
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
        <Box className="fixed-bottom-buttons">
          <Box className="button-container">
            <ChatButton />
          </Box>
          <Box className="button-container">
            <MapButton />
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
};

export default ItineraryPage;
