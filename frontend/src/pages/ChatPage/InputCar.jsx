import { useState } from 'react';
import { Box, TextField } from '@mui/material';
import PropTypes from 'prop-types';
import './ChatPage.css';

const CarInputBar = ({ handleKeyDown, onValueChange }) => {
  const [carInfo, setCarInfo] = useState(['', '', '']);

  const handleCarInfoChange = (index, value) => {
    const updated = [...carInfo];
    updated[index] = value;
    setCarInfo(updated);
    if (onValueChange) onValueChange(updated);
  };

  const fields = [
    { placeholder: 'Year', value: carInfo[0] },
    { placeholder: 'Make', value: carInfo[1] },
    { placeholder: 'Model', value: carInfo[2] },
  ];

  return (
    <Box sx={{ display: 'flex', gap: 1, flex: 1 }}>
      {fields.map((field, index) => (
        <TextField
          key={index}
          className="split-input-bar"
          placeholder={field.placeholder}
          value={field.value}
          onChange={(e) => handleCarInfoChange(index, e.target.value)}
          onKeyDown={handleKeyDown}
          size="small"
        />
      ))}
    </Box>
  );
};

CarInputBar.propTypes = {
  handleKeyDown: PropTypes.func,
  onValueChange: PropTypes.func,
};

export default CarInputBar;
