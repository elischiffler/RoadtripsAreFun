import { useRef, useState } from 'react';
import { Box, TextField, IconButton, InputAdornment } from '@mui/material';
import ArrowUpwardRoundedIcon from '@mui/icons-material/ArrowUpwardRounded';
import PropTypes from 'prop-types';
import './ChatPage.css';

/**
 * ChatInput — persistent free-text bar for talking to the conversational agent.
 *
 * The send icon sits inside the input bubble. Text is routed to the agent via
 * `onSubmit(text)` (which the caller wires to submit('chat_message')).
 *
 * Props:
 *   onSubmit  {fn}       – called with the trimmed text when the user submits
 *   disabled  {boolean}  – disables input while a turn is in flight
 */
const ChatInput = ({ onSubmit, disabled }) => {
  const [value, setValue] = useState('');
  const sending = useRef(false);

  const handleSend = async () => {
    const text = value.trim();
    if (!text || disabled || sending.current) return;
    sending.current = true;
    try {
      if ((await onSubmit(text)) !== false) setValue('');
    } finally {
      sending.current = false;
    }
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
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                aria-label="Send message"
                className="chat-send-button"
                disableRipple
                onClick={handleSend}
                disabled={disabled || !value.trim()}
                edge="end"
              >
                <ArrowUpwardRoundedIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ),
        }}
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: '24px',
            backgroundColor: 'color-mix(in srgb, var(--cream-light) 65%, transparent)',
            color: '#000',
            minHeight: '48px',
          },
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: 'var(--cream-dark)',
          },
        }}
      />
    </Box>
  );
};

ChatInput.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

export default ChatInput;
