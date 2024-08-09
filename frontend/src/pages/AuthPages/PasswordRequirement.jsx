import React from "react";
import { Box, Typography } from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import "./AuthPage.css";

const PasswordRequirement = ({ fulfilled, text }) => (
  <Box className="requirement">
    {fulfilled ? (
      <CheckIcon sx={{ color: "green" }} />
    ) : (
      <CloseIcon sx={{ color: "gray" }} />
    )}
    <Typography variant="body2">{text}</Typography>
  </Box>
);

export default PasswordRequirement;
