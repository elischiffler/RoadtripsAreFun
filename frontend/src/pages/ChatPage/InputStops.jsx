import Slider from "@mui/material/Slider";

const StopSlider = ({ UserChatData }) => {

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
