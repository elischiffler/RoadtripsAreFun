import Slider from "@mui/material/Slider";

const BudgetSlider = ({ UserChatData }) => {

  const handleChange = (event, newValue) => {
    // Update the stops value in UserChatData
    UserChatData.budget = newValue;
  };

// Function to format the value with a dollar sign
const formatValue = (value) => {
    return `$${value}`;
  };

  return (
    <Slider
      className="input-slider"
      defaultValue={UserChatData.minHotelBudget}
      aria-label="Stop slider"
      valueLabelDisplay="auto"
      min={UserChatData.minHotelBudget}
      max={UserChatData.minHotelBudget * 2}
      onChange={handleChange}
      valueLabelFormat={formatValue}
    />
  );
};

export default BudgetSlider;