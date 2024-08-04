import React from "react";
import { Button, Typography } from "@mui/material";
import KeyboardReturnIcon from "@mui/icons-material/KeyboardReturn";
import { Link } from "react-router-dom";

const ReturnToChatButton = () => {
  return (
    <Link
      to="/chat"
      style={{ textDecoration: "none", display: "flex", alignItems: "center" }}
    >
      <Button
        variant="contained"
        color="secondary"
        startIcon={<KeyboardReturnIcon />}
        sx={{
          mt: 2,
          display: "flex",
          alignItems: "center",
          width: "fit-content",
          whiteSpace: "nowrap",
        }}
      >
        <Typography variant="body1" sx={{ ml: 1 }}>
          Chat
        </Typography>
      </Button>
    </Link>
  );
};

export default ReturnToChatButton;
