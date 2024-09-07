import { React, useContext } from "react";
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


const ItineraryPage = () => {

  // Retrieve the global instance of UserData
  const { UserData } = useContext(UserDataContext);
  // Grab the chat logs and make sure everything is defined
  const ChatLogsData = UserData?.chatlogs || {};
  const UserChatData = ChatLogsData?.chatdata?.[ChatLogsData.currentId - 1];
  console.log(ChatLogsData);
  console.log(UserChatData);

  if (!UserChatData || !UserChatData.itinerary) {
    return (
      <Container className="itinerary-page" maxWidth={false} disableGutters>
        <Box className="fixed-top-box">
          <LogoButton />
          <Box className="title">
            <Typography variant="h6" color="white.black">
              No Itinerary Available
            </Typography>
          </Box>
        </Box>
      </Container>
    );
  }


  return (
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
        {UserChatData.itinerary.map((day, index) => (
          <Box key={index} className="day-box">
            <Box className="day-header">
              <Typography variant="h6">{day['date']}</Typography>
            </Box>
            <Box>
              {day['stops'].map((activity, idx) => (
                activity['address'] ?(
                <Box key={idx} className="activity-box">
                  <Typography variant="body1">
                    {activity['url']? // Conditionally render the name
                      // Makes the name clickable and navigates you to the booking link in a new tab
                      (
                        <a href={activity['url']}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="activity-link">
                          {activity['name']}
                        </a>
                      ):
                      (activity['name'])}
                  </Typography>
                  <Typography variant="body2" className="activity-time">
                    {`Arrival time: ${activity['time']}`}
                  </Typography>
                  <Typography variant="body2" className="activity-time">
                    {`Address: ${activity['address']}`}
                  </Typography>
                  <Typography variant="body2" className="activity-time">
                    {activity['price']?
                      `Price: $${activity['price']}`:
                      null
                    }
                  </Typography>
                </Box>):
                (<Box key={idx} className="activity-box">
                  <Typography variant="body1">{activity['name']}</Typography>
                  <Typography variant="body2" className="activity-time">
                    {`Departure time: ${activity['time']}`}
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
          <MapButton route={UserChatData.route}/>
        </Box>
      </Box>
    </Container>
  );
};

export default ItineraryPage;