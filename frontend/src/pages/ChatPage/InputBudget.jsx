import Slider from "@mui/material/Slider";

const BudgetSlider = ({ UserChatData }) => {

  const handleChange = (event, newValue) => {
    // Update the stops value in UserChatData
    UserChatData.budget = newValue;
  };

  return (
    <Slider
      className="input-slider"
      defaultValue={UserChatData.minHotelBudget}
      aria-label="Stop slider"
      valueLabelDisplay="auto"
      min={UserChatData.minHotelBudget}
      max={UserChatData.minHotelBudget * 2}
      onChange={handleChange} // Use the handler function
    />
  );
};

export default BudgetSlider;