import React from "react";
import { Button, Box, Typography } from "@mui/material";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import { Link } from "react-router-dom";


const ItineraryButton = ({ itinerary }) => {
  return (
    <Link
      to={itinerary? "/itinerary": '#'}
      className="link"
      onClick={(e) => {
        if (!itinerary) {
          e.preventDefault(); // Prevent routing if the value is not set
        }
      }}
    >
      <Button
        variant="contained"
        className="button"
        disabled={!itinerary}
      >
        <Box className="button-content">
          <FormatListBulletedIcon className="button-icon" />{" "}
          {/* Adjust margin as needed */}
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
