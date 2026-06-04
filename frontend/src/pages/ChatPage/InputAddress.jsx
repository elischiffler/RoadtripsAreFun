import { useState, useEffect } from 'react';
import { Box, TextField } from '@mui/material';
import PropTypes from 'prop-types';
import './ChatPage.css';

const AddressBar = ({ UserChatData, handleKeyDown }) => {
  // Initialize the address based on the type of location (start or end)
  let initialAddress;
  if (UserChatData.locationType === 'start') {
    // Default to an empty array if startAddress is not defined
    initialAddress = UserChatData?.startAddress || ['', '', '', ''];
  } else if (UserChatData.locationType === 'end') {
    // Default to an empty array if endAddress is not defined
    initialAddress = UserChatData?.endAddress || ['', '', '', ''];
  }

  // Initialize state with the values from UserChatData
  const [address, setAddress] = useState(initialAddress);

  // Sync the address state with UserChatData on initial render or when UserChatData changes
  useEffect(() => {
    if (UserChatData) {
      if (UserChatData.locationType === 'start') {
        // Update state with the start address from UserChatData
        setAddress(UserChatData.startAddress);
      } else if (UserChatData.locationType === 'end') {
        // Update state with the end address from UserChatData
        setAddress(UserChatData.endAddress);
      }
    }
  }, [UserChatData]);

  // Handles the change of address input fields
  const handleAddressChange = (index, value) => {
    // Create a copy of the address array and update the specific index
    const updatedAddress = [...address];
    updatedAddress[index] = value;
    setAddress(updatedAddress);

    // Update the corresponding address in UserChatData based on location type
    if (UserChatData) {
      if (UserChatData.locationType === 'start') {
        UserChatData.startAddress = updatedAddress;
      } else if (UserChatData.locationType === 'end') {
        UserChatData.endAddress = updatedAddress;
      }
    }
  };

  // Define the placeholders and values for each address input field
  const addressFields = [
    { placeholder: 'Street Address', value: address[0] },
    { placeholder: 'City', value: address[1] },
    { placeholder: 'State', value: address[2] },
    { placeholder: 'ZIP Code', value: address[3] },
  ];

  return (
    <Box>
      {addressFields.map((field, index) => (
        <TextField
          key={index}
          className="split-input-bar"
          placeholder={field.placeholder}
          value={field.value}
          onChange={(e) => handleAddressChange(index, e.target.value)}
          onKeyDown={handleKeyDown}
        />
      ))}
    </Box>
  );
};

AddressBar.propTypes = {
  UserChatData: PropTypes.object.isRequired,
  handleKeyDown: PropTypes.func.isRequired,
};

export default AddressBar;
