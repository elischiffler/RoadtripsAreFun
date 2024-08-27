import React from "react";
import { Button, Box, Typography, Tooltip } from "@mui/material";
import MapIcon from "@mui/icons-material/Map";
import { Link } from "react-router-dom";

// MapButton component that conditionally renders a link to the map page
const MapButton = ({ route }) => {
  const button = (
    <Button
      variant="contained"
      color="green"
      startIcon={<MapIcon className="button-icon" />} // Add map icon to the button
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
      to={route ? "/map" : "#"} // Prevent navigation if 'route' is not provided
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

export default MapButton;