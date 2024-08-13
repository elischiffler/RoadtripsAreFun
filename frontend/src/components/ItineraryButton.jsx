import React from "react";
import { Button, Box, Typography } from "@mui/material";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import { Link } from "react-router-dom";


const ItineraryButton = () => {
  return (
    <Link
      to="/itinerary"
      className="link"
    >
      <Button
        variant="contained"
        className="button"
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
