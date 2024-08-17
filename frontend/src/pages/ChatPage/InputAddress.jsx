import React from "react";
import { Box, TextField } from "@mui/material";
import "./ChatPage.css";

const AddressBar = () => {
  return (
    <Box>
      <TextField
        className="input-address"
        placeholder="Street Address"
        variant="outlined"
      />
      <TextField
        className="input-address"
        placeholder="City"
        variant="outlined"
      />
      <TextField
        className="input-address"
        placeholder="State"
        variant="outlined"
      />
      <TextField
        className="input-address"
        placeholder="ZIP Code"
        variant="outlined"
      />
    </Box>
  );
};

export default AddressBar;
