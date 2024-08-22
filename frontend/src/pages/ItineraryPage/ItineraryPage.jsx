import { React } from "react";
import {
  Box,
  Typography,
  Container,
} from "@mui/material";
import LogoButton from "../../components/LogoButton";
import ChatButton from "../../components/buttons/ChatButton";
import MapButton from "../../components/buttons/MapButton";
import { UserDataContext } from "../../states/UserDataContext";
import "./ItineraryPage.css";
import { useContext, useEffect } from "react"
import { generateItinerary } from "./generateItinerary";


const ItineraryPage = () => {

  // Retrieve the global instance of UserData
  const UserData = useContext(UserDataContext);
  // Use the UserChatData
  const UserChatData = UserData.chat;

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

  useEffect( ()=>{
    if(UserChatData.route){
      // Generate the itinerary on the first render
      UserChatData.itinerary = generateItinerary(UserChatData.route);
      console.log("The itinerary: ", UserChatData.itinerary);
    }
  }, [])

  return (
    <Container className="itinerary-page" maxWidth={false} disableGutters>
      {/* Fixed Top Box */}
      {console.log(UserChatData.route)};
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
  );
};

export default ItineraryPage;