import React from "react";
import { Button, Box, Typography, Tooltip } from "@mui/material";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import { Link } from "react-router-dom";

// ItineraryButton component that conditionally renders a link to the itinerary page
const ItineraryButton = ({ route }) => {
  const button = (
    <Button
    variant="contained"
    color="green"
    startIcon={<FormatListBulletedIcon className="button-icon" />} // Add itinerary icon to the button
    className="button"
    disabled={!route} // Disable button if no route
  >
    <Box className="button-content">
      <Typography variant="body1" className="typography">
        Map
      </Typography>
    </Box>
  </Button>
  );

  return (
    <Link
      to={route ? "/itinerary" : "#"} // Prevent navigation if route is not provided
      className="link"
      onClick={(e) => {
        if (!route) e.preventDefault(); // Disable link if no route
      }}
    >
            {/* Conditionally wrap the button in a Tooltip if the button is disabled */}
            {!route ? (
        <Tooltip title="Please answer the questions first" placement="right" arrow>
          <span>
          {button}
          </span>
        </Tooltip>
      ) : (
        button
      )}
    </Link>
  );
};

export default ItineraryButton;