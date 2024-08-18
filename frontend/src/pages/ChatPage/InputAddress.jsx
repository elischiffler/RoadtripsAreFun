import React, { useState, useEffect } from "react";
import { Box, TextField } from "@mui/material";
import "./ChatPage.css";

const AddressBar = ({ UserChatData }) => {
  // Ensure UserChatData and address are defined, using default values if not
  const initialAddress = UserChatData?.address || ["", "", "", ""];

  // Initialize state with the values from UserChatData
  const [address, setAddress] = useState(initialAddress);

  // Sync address state with UserChatData on initial render or when UserChatData changes
  useEffect(() => {
    if (UserChatData && UserChatData.address) {
      setAddress(UserChatData.address);
    }
  }, [UserChatData]);

  const handleAddressChange = (index, value) => {
    const updatedAddress = [...address];
    updatedAddress[index] = value;
    setAddress(updatedAddress);

    // Update the UserChatData instance's address property if UserChatData is defined
    if (UserChatData) {
      UserChatData.address = updatedAddress;
    }
  };

  const addressFields = [
    { placeholder: "Street Address", value: address[0] },
    { placeholder: "City", value: address[1] },
    { placeholder: "State", value: address[2] },
    { placeholder: "ZIP Code", value: address[3] },
  ];

  return (
    <Box>
      {addressFields.map((field, index) => (
        <TextField
          key={index}
          className="input-address"
          placeholder={field.placeholder}
          value={field.value}
          onChange={(e) => handleAddressChange(index, e.target.value)}
        />
      ))}
    </Box>
  );
};

export default AddressBar;
