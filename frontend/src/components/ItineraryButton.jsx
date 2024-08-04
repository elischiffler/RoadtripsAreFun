import React from "react";
import { Button, Box, Typography } from "@mui/material";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import { Link } from "react-router-dom";

const ItineraryButton = () => {
  return (
    <Link
      to="/itinerary"
      style={{ textDecoration: "none", width: "100%", display: "block" }}
    >
      <Button
        variant="contained"
        color="secondary"
        sx={{ mb: 1, width: "100%", display: "flex", alignItems: "center" }}
      >
        <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
          <FormatListBulletedIcon sx={{ mr: 1 }} />{" "}
          {/* Adjust margin as needed */}
          <Typography variant="body1" sx={{ flex: 1, textAlign: "center" }}>
            Itinerary
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default ItineraryButton;
