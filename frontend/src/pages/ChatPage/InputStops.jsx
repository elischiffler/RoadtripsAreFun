import React, { useContext } from "react";
import Slider from "@mui/material/Slider";
import { UserChatDataContext } from "../../states/UserChatDataContext";

const StopSlider = () => {
  // Access UserChatData from the context
  const UserChatData = useContext(UserChatDataContext);

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
      min={0}
      max={10}
      onChange={handleChange} // Use the handler function
    />
  );
};

export default StopSlider;
