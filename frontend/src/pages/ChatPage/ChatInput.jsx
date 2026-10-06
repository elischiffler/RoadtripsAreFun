import { useContext, useRef, useState } from 'react';
import { Box, TextField, IconButton, InputAdornment } from '@mui/material';
import ArrowUpwardRoundedIcon from '@mui/icons-material/ArrowUpwardRounded';
import PropTypes from 'prop-types';
import './ChatPage.css';
import { UserDataContext } from '../../states/UserDataContext';
import { getSession, isCurrentSession } from '../../services/session';

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
const ChatInput = ({ onSubmit, disabled, draftKey = 'chat' }) => {
  const context = useContext(UserDataContext);
  const drafts = context?.drafts;
  const [value, setValue] = useState(() => drafts?.current.get(draftKey) ?? '');
  const updateValue = (text) => {
    setValue(text);
    drafts?.current.set(draftKey, text);
  };
  const sending = useRef(false);

  const handleSend = async () => {
    const text = value.trim();
    if (!text || disabled || sending.current) return;
    sending.current = true;
    try {
      const session = getSession();
      if ((await onSubmit(text)) !== false && isCurrentSession(session)) updateValue('');
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
        onChange={(e) => updateValue(e.target.value)}
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
  draftKey: PropTypes.string,
};

export default ChatInput;
