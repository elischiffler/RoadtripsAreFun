import React, { useContext } from "react";
import Slider from "@mui/material/Slider";
import { UserDataContext } from "../../states/UserDataContext";

const StopSlider = () => {
  // Retrieve the global instance of UserData
  const UserData = useContext(UserDataContext);
  // Grab the chat logs
  const ChatLogsData = UserData.chatlogs
  // Grab Users chat data depending on log
  const UserChatData = ChatLogsData.chatdata;

  const handleChange = (event, newValue) => {
    // Update the stops value in UserChatData
    UserChatData.stops = newValue;
    console.log(UserChatData.stops)
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
