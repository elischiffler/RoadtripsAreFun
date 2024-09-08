import Slider from "@mui/material/Slider";

const BudgetSlider = ({ UserChatData, handleKeyDown }) => {

  const handleChange = (event, newValue) => {
    // Update the stops value in UserChatData
    UserChatData.hotelBudget = newValue;
  };

// Function to format the value with a dollar sign
const formatValue = (value) => {
    return `$${value}`;
  };

  return (
    <Slider
      className="input-slider"
      defaultValue={UserChatData.hotelBudget}
      aria-label="Stop slider"
      valueLabelDisplay="auto"
      min={UserChatData.hotelBudget}
      max={UserChatData.hotelBudget * 2}
      onChange={handleChange}
      valueLabelFormat={formatValue}
      onKeyDown={handleKeyDown}
    />
  );
};

export default BudgetSlider;