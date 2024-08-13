import React from "react";
import { Button, Box, Typography } from "@mui/material";
import MapIcon from "@mui/icons-material/Map";
import { Link } from "react-router-dom";

const MapButton = () => {
  return (
    <Link
      to="/map"
      className="link"
    >
      <Button
        variant="contained"
        color="green"
        startIcon={<MapIcon className="button-icon" />}
        className="button"
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
