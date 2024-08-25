import React from "react";
import { Button, Box, Typography } from "@mui/material";
import MapIcon from "@mui/icons-material/Map";
import { Link } from "react-router-dom";

const MapButton = ({ route }) => {
  return (
    <Link
      to={route? "/map": "#"}
      className="link"
      onClick={(e) => {
        if (!route) {
          e.preventDefault(); // Prevent routing if the value is not set
        }
      }}
    >
      <Button
        variant="contained"
        color="green"
        startIcon={<MapIcon className="button-icon" />}
        className="button"
        disabled={!route}
      >
        <Box className="button-content">
          <Typography
            variant="body1"
            className="typography"
          >
            Map
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default MapButton;
