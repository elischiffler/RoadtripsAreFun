import { useState } from 'react';
import { Box, TextField, Button } from '@mui/material';
import PropTypes from 'prop-types';
import './ChatPage.css';

/**
 * ChatInput — persistent free-text bar for talking to the conversational agent.
 *
 * Mirrors the LocationInput MUI text-field + send-button pattern and reuses the
 * existing `inline-input-row` / `send-button` styles. It coexists with the
 * scripted per-step widgets: whatever the user types here is routed to the
 * agent via `onSubmit(text)` (which the caller wires to submit('chat_message')).
 *
 * Props:
 *   onSubmit  {fn}       – called with the trimmed text when the user submits
 *   disabled  {boolean}  – disables input while a turn is in flight
 */
const ChatInput = ({ onSubmit, disabled }) => {
  const [value, setValue] = useState('');

  const handleSend = () => {
    const text = value.trim();
    if (!text) return;
    onSubmit(text);
    setValue('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Box className="inline-input-row">
      <TextField
        className="split-input-bar"
        placeholder="Ask JourneyGenie anything about your trip…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        fullWidth
        autoComplete="off"
        size="small"
        inputProps={{ 'aria-label': 'Chat message' }}
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: '10px',
            backgroundColor: 'var(--cream-light)',
          },
        }}
      />
      <Button variant="contained" className="send-button" onClick={handleSend} disabled={disabled}>
        Send
      </Button>
    </Box>
  );
};

ChatInput.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

export default ChatInput;
