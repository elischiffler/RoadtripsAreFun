import * as React from "react";
import {
  Box,
  Container,
  CssBaseline,
  ThemeProvider,
  createTheme,
  Button,
  Typography,
  TextField,
} from "@mui/material";
import { Link } from "react-router-dom";
import LogoButton from "../components/LogoButton";
import InfoIcon from "@mui/icons-material/Info";

const customTheme = createTheme({
  palette: {
    primary: {
      main: "#4464AD",
    },
    secondary: {
      main: "#6DB1BF",
    },
    pink: {
      main: "#E5D0E3",
    },
    purple: {
      main: "#38023B",
    },
    dark: {
      main: "#071108",
    },
  },
});

export default function HomePage() {
  return (
    <ThemeProvider theme={customTheme}>
      <CssBaseline />
      <Container
        maxWidth={false}
        disableGutters
        sx={{ width: "100vw", height: "100vh", overflowX: "hidden" }} // Prevent horizontal overflow
      >
        {/* Top Box */}
        <Box
          sx={{
            width: "100%",
            height: "10%",
            bgcolor: "primary.main.light",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingX: 2,
          }}
        >
          <LogoButton />

          <Box>
            <Button
              variant="contained"
              color="primary"
              component={Link}
              to="/login"
              sx={{ marginRight: 2 }}
            >
              Login
            </Button>
            <Button
              variant="contained"
              color="secondary"
              component={Link}
              to="/signup"
            >
              Signup
            </Button>
          </Box>
        </Box>

        {/* Main Content Box */}
        <Box
          sx={{
            bgcolor: "primary.main",
            height: "45%", // Adjusted to leave space for the bottom section
            width: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            color: "white",
          }}
        >
          <Typography variant="h2" component="h1" sx={{ mb: 1 }}>
            Journey Genie
          </Typography>
          <Typography variant="h5" component="h2" sx={{ mb: 3 }}>
            Plan a trip in minutes!
          </Typography>
          <Button variant="contained" color="secondary">
            Get Started
          </Button>
        </Box>

        {/* Bottom Section */}
        <Box
          sx={{
            width: "100%",
            height: "50%", // Increased to extend further
            bgcolor: "primary.main", // Same color as the main section
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 2,
            position: "relative",
          }}
        >
          <Box
            sx={{
              display: "grid",
              gap: 2,
              gridTemplateColumns: "repeat(3, 1fr)",
              width: "100%",
              maxWidth: "1200px", // Ensure it doesn't exceed viewport width
              boxSizing: "border-box", // Include padding and border in the element's total width and height
            }}
          >
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
              <Box
                key={index}
                sx={{
                  bgcolor: "rgba(229, 208, 227, 0.75)", // Transparent pink
                  borderRadius: 2,
                  padding: 2,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  position: "relative",
                  paddingLeft: 4, // Increased padding to accommodate InfoIcon
                  boxSizing: "border-box", // Ensure padding and border are included in width
                }}
              >
                <InfoIcon
                  sx={{
                    position: "absolute",
                    top: 8,
                    left: 8,
                    color: "primary.main",
                  }}
                />
                <Typography
                  variant="h6"
                  sx={{ fontWeight: "bold", mb: 1, marginLeft: "20px" }} // Adjust margin for title
                >
                  {item.title}
                </Typography>
                <Typography variant="body2" sx={{ marginLeft: "20px" }}>
                  {item.description}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}
