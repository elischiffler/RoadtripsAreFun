import React, { useState, useEffect } from "react";
import { Box, TextField } from "@mui/material";
import "./ChatPage.css";

const CarInputBar = ({ UserChatData }) => {
  // Initialize state with the values from UserChatData
  const [carInfo, setCarInfo] = useState(UserChatData.carDetails || ["", "", ""]);

  // Sync the carInfo state with UserChatData on initial render or when UserChatData changes
  useEffect(() => {
    if (UserChatData && UserChatData.carDetails) {
      setCarInfo(UserChatData.carDetails);
    }
  }, [UserChatData]);

  // Handles the change of car info input fields
  const handleCarInfoChange = (index, value) => {
    // Create a copy of the carInfo array and update the specific index
    const updatedCarInfo = [...carInfo];
    updatedCarInfo[index] = value;
    setCarInfo(updatedCarInfo);

    // Update the corresponding car info in UserChatData
    if (UserChatData) {
      UserChatData.carDetails = updatedCarInfo;
    }
  };

  // Define the placeholders and values for each car info input field
  const carInfoFields = [
    { placeholder: "Year", value: carInfo[0] },
    { placeholder: "Make", value: carInfo[1] },
    { placeholder: "Model", value: carInfo[2] },
  ];

  return (
    <Box>
      {carInfoFields.map((field, index) => (
        <TextField
          key={index}
          className="split-input-bar"
          placeholder={field.placeholder}
          value={field.value}
          onChange={(e) => handleCarInfoChange(index, e.target.value)}
        />
      ))}
    </Box>
  );
};

export default CarInputBar;