import Slider from '@mui/material/Slider';
import PropTypes from 'prop-types';

const StopSlider = ({ UserChatData, handleKeyDown }) => {
  const handleChange = (event, newValue) => {
    // Update the stops value in UserChatData
    UserChatData.stops = newValue;
  };

  return (
    <Slider
      className="input-slider"
      defaultValue={1}
      aria-label="Stop slider"
      valueLabelDisplay="auto"
      min={1}
      max={10}
      onChange={handleChange} // Use the handler function
      onKeyDown={handleKeyDown}
    />
  );
};

StopSlider.propTypes = {
  UserChatData: PropTypes.object.isRequired,
  handleKeyDown: PropTypes.func.isRequired,
};

export default StopSlider;
