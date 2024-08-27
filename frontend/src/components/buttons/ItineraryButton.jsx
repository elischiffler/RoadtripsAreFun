import React from "react";
import { Button, Box, Typography } from "@mui/material";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import { Link } from "react-router-dom";

// ItineraryButton component that conditionally renders a link to the itinerary page
const ItineraryButton = ({ itinerary }) => {
  return (
    <Link
      to={itinerary ? "/itinerary" : "#"} // If 'itinerary' is provided, link to the itinerary page; otherwise, use a placeholder link
      className="link"
      onClick={(e) => {
        if (!itinerary) {
          e.preventDefault(); // Prevent navigation if 'itinerary' is not set
        }
      }}
    >
      <Button
        variant="contained"
        className="button"
        disabled={!itinerary} // Disable the button if 'itinerary' is not set
      >
        <Box className="button-content">
          <FormatListBulletedIcon className="button-icon" />{" "}
          {/* Icon for the button, adjust margin as needed */}
          <Typography
            variant="body1"
            className="typography"
          >
            Itinerary
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default ItineraryButton;