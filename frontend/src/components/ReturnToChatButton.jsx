import React from "react";
import { Button, Box, Typography } from "@mui/material";
import KeyboardReturnIcon from "@mui/icons-material/KeyboardReturn";
import { Link } from "react-router-dom";

const ReturnToChatButton = () => {
  return (
    <Link to="/chat" style={{ textDecoration: "none" }}>
      <Button
        variant="contained"
        color="secondary"
        startIcon={<KeyboardReturnIcon />}
        sx={{ mt: 2, display: "flex", alignItems: "center" }}
      >
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <Typography variant="body1" sx={{ ml: 1 }}>
            Chat
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default ReturnToChatButton;
