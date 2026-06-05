import { useState } from 'react';
import { TextField, InputAdornment } from '@mui/material';
import PropTypes from 'prop-types';

const BudgetSlider = ({ UserChatData, handleKeyDown, onValueChange }) => {
  const min = UserChatData?.hotelBudget ?? 0;
  const [value, setValue] = useState(min);

  const handleChange = (e) => {
    const num = Math.max(min, parseInt(e.target.value, 10) || min);
    setValue(num);
    if (onValueChange) onValueChange(num);
  };

  return (
    <TextField
      type="number"
      value={value}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      inputProps={{ min }}
      size="small"
      label="Hotel budget"
      InputProps={{
        startAdornment: <InputAdornment position="start">$</InputAdornment>,
      }}
      sx={{ width: 200, backgroundColor: 'var(--cream-light)', borderRadius: '8px' }}
    />
  );
};

BudgetSlider.propTypes = {
  UserChatData: PropTypes.object,
  handleKeyDown: PropTypes.func,
  onValueChange: PropTypes.func,
};

export default BudgetSlider;
