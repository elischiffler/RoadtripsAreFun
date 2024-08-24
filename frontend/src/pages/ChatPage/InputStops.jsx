import React, { useContext } from "react";
import Slider from "@mui/material/Slider";
import { UserDataContext } from "../../states/UserDataContext";

const StopSlider = () => {
  // Retrieve the global instance of UserData
  const UserData = useContext(UserDataContext);
  // Use the UserChatData
  const UserChatData = UserData.chat;

  const handleChange = (event, newValue) => {
    // Update the stops value in UserChatData
    UserChatData.stops = newValue;
  };

  return (
    <Slider
      className="num-stops-slider"
      defaultValue={0}
      aria-label="Stop slider"
      valueLabelDisplay="auto"
      min={1}
      max={10}
      onChange={handleChange} // Use the handler function
    />
  );
};

export default StopSlider;
