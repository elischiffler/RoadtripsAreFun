import React from "react";
import { Button, Box, Typography } from "@mui/material";
import KeyboardReturnIcon from "@mui/icons-material/KeyboardReturn";
import { Link } from "react-router-dom";

const ChatButton = () => {
  return (
    <Link
      to="/chat"
      style={{ textDecoration: "none", width: "100%", display: "block" }}
    >
      <Button
        variant="contained"
        color="secondary"
        startIcon={<KeyboardReturnIcon />}
        sx={{ mt: 2, width: "100%", display: "flex", alignItems: "center" }}
      >
        <Box sx={{ display: "flex", alignItems: "center", width: "100%" }}>
          <Typography
            variant="body1"
            sx={{ ml: 1, width: "100%", textAlign: "center" }}
          >
            Chat
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default ChatButton;
