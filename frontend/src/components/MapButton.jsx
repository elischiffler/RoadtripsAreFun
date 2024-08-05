import React from "react";
import { Button, Box, Typography } from "@mui/material";
import MapIcon from "@mui/icons-material/Map";
import { Link } from "react-router-dom";

const MapButton = () => {
  return (
    <Link
      to="/map"
      style={{ textDecoration: "none", width: "100%", display: "block" }}
    >
      <Button
        variant="contained"
        color="secondary"
        startIcon={<MapIcon />}
        sx={{ mt: 2, width: "100%", display: "flex", alignItems: "center" }}
      >
        <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
          <Typography
            variant="body1"
            sx={{ ml: 1, width: "100%", textAlign: "center" }}
          >
            Map
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default MapButton;
