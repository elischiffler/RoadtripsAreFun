import { React, useContext, useEffect,  } from "react";
import {
  Box,
  Container,
  Button,
  Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import LogoButton from "../../components/LogoButton";
import InfoIcon from "@mui/icons-material/Info";
import VerifiedUserIcon from "@mui/icons-material/VerifiedUser";
import "./HomePage.css";
import { UserDataContext } from "../../states/UserDataContext";

const isAuthenticated = () => {
  const accessToken = sessionStorage.getItem("accessToken");
  return !!accessToken;
};

export default function HomePage() {
  const navigate = useNavigate();
  const authenticated = isAuthenticated();

  const handleGetStartedClick = () => {
    if (authenticated) {
      navigate("/chat");
    } else {
      navigate("/login");
    }
  };
  
  // Retrieve global instance of data
  const { setUserData, getUserData } = useContext(UserDataContext);

  // Reset the UserData to be the last saved data if renavigating to chat
  useEffect(()=>{
    const prevData = getUserData()
    if(prevData){
      setUserData(prevData)
    }
  }, []);


  return (
    <Container className="home-page" maxWidth={false} disableGutters>
      <Box className="top-box">
        <LogoButton />
        <Box>
          {authenticated ? (
            <VerifiedUserIcon />
          ) : (
            <>
              <Button
                variant="contained"
                component={Link}
                to="/login"
                className="login-button"
              >
                Login
              </Button>
              <Button
                variant="contained"
                component={Link}
                to="/signup"
                className="signup-button"
              >
                Signup
              </Button>
            </>
          )}
        </Box>
      </Box>

      <Box className="main-content-box">
        <Typography variant="h2" component="h1">
          Journey Genie
        </Typography>
        <Typography variant="h5" component="h2">
          Plan a trip in minutes!
        </Typography>
        <Button
          variant="contained"
          onClick={handleGetStartedClick}
          className="get-started-button"
        >
          Get Started
        </Button>
      </Box>

      <Box className="bottom-section">
        <Box className="info-container">
          {[
            {
              title: "Personalized Itineraries",
              description:
                "We create customized travel itineraries based on your preferences, ensuring that you visit destinations and attractions that align with your interests and time constraints.",
            },
            {
              title: "Efficient Planning",
              description:
                "We simplify trip planning by suggesting optimal routes, rest stops, fuel stations, and accommodations, saving you time and effort in organizing your trips.",
            },
            {
              title: "Enhanced Safety",
              description:
                "By offering safety tips and monitoring general driving conditions, we can help prevent accidents and ensure you are aware of any potential hazards on your route.",
            },
            {
              title: "Cost Savings",
              description:
                "We can suggest cost-effective travel options, such as fuel-efficient routes, affordable accommodations, and nearby discounts or deals, helping you manage your budget more effectively.",
            },
            {
              title: "Enriched Travel Experience",
              description:
                "With recommendations for local attractions, dining spots, and hidden gems, we enhance your overall travel experience by guiding you to unique and memorable destinations you might otherwise miss.",
            },
            {
              title: "User-Friendly Interface",
              description:
                "Our intuitive design ensures ease of use, allowing you to quickly and effortlessly plan your trips, make adjustments, and access valuable information on the go.",
            },
          ].map((item, index) => (
            <Box key={index} className="info-item">
              <InfoIcon className="info-icon" />
              <Typography variant="h6" className="info-title">
                {item.title}
              </Typography>
              <Typography variant="body2" className="info-description">
                {item.description}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Container>
  );
}
