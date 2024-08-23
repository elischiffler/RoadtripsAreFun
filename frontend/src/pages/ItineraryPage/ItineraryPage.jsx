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
import { useContext } from "react"


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
        {UserChatData.itinerary.map((day, index) => (
          <Box key={index} className="day-box">
            <Box className="day-header">
              <Typography variant="h6">{day['date']}</Typography>
            </Box>
            <Box>
              {day['stops'].map((activity, idx) => (
                activity['address'] ?(
                <Box key={idx} className="activity-box">
                  <Typography variant="body1">{activity['name']}</Typography>
                  <Typography variant="body2" className="activity-time">
                    {`Arrival time: ${activity['time']}`}
                  </Typography>
                  <Typography variant="body2" className="activity-time">
                    {`Address: ${activity['address']}`}
                  </Typography>
                </Box>):
                (<Box key={idx} className="activity-box">
                  <Typography variant="body1">{activity['name']}</Typography>
                  <Typography variant="body2" className="activity-time">
                    {activity['time']}
                  </Typography>
                </Box>)
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