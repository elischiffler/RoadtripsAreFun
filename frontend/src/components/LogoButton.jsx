import React from "react";
import { IconButton } from "@mui/material";
import MinorCrashIcon from "@mui/icons-material/MinorCrash";
import { useNavigate } from "react-router-dom";

const LogoButton = () => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate("/");
  };

  return (
    <IconButton onClick={handleClick} sx={{ color: "inherit" }}>
      <MinorCrashIcon sx={{ fontSize: 40 }} />
    </IconButton>
  );
};

export default LogoButton;
