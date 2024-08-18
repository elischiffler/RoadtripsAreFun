import React, { useState, useEffect, useContext } from "react";
import { Box, TextField } from "@mui/material";
import "./ChatPage.css";
import { UserChatDataContext } from "../../states/UserChatDataContext";

const AddressBar = () => {
  // Grabs the global instance of UserChatData
  const UserChatData = useContext(UserChatDataContext);

  // Ensure UserChatData and address are defined, using default values if not
  let initialAddress;
  if (UserChatData.locationType == "start") {
    initialAddress = UserChatData?.startAddress || ["", "", "", ""];
  } else if (UserChatData.locationType == "end") {
    initialAddress = UserChatData?.endAddress || ["", "", "", ""];
  }

  // Initialize state with the values from UserChatData
  const [address, setAddress] = useState(initialAddress);

  // Sync address state with UserChatData on initial render or when UserChatData changes
  useEffect(() => {
    if (UserChatData) {
      if (UserChatData.locationType == "start") {
        setAddress(UserChatData.startAddress);
      } else if (UserChatData.locationType == "end") {
        setAddress(UserChatData.endAddress);
      }
    }
  }, [UserChatData]);

  const handleAddressChange = (index, value) => {
    const updatedAddress = [...address];
    updatedAddress[index] = value;
    setAddress(updatedAddress);

    // Update the UserChatData instance's address property based on type
    if (UserChatData) {
      if (UserChatData.locationType === "start") {
        UserChatData.startAddress = updatedAddress;
      } else if (UserChatData.locationType === "end") {
        UserChatData.endAddress = updatedAddress;
      }
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
