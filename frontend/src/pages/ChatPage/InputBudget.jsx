import { useState } from 'react';
import { Box, TextField, InputAdornment, Button } from '@mui/material';
import PropTypes from 'prop-types';

const QUICK_STEPS = [50, 100, 500];

const BudgetSlider = ({ UserChatData, handleKeyDown, onValueChange }) => {
  const min = UserChatData?.hotelBudget ?? 0;
  const [value, setValue] = useState(min);

  const update = (next) => {
    const clamped = Math.max(min, next);
    setValue(clamped);
    if (onValueChange) onValueChange(clamped);
  };

  const handleChange = (e) => {
    // Allow free typing — only clamp on blur so the user can clear and retype
    const raw = e.target.value;
    if (raw === '' || raw === '-') {
      setValue(raw);
      return;
    }
    const num = parseInt(raw, 10);
    if (!isNaN(num)) {
      setValue(num);
      if (onValueChange) onValueChange(Math.max(min, num));
    }
  };

  const handleBlur = () => {
    const num = parseInt(value, 10);
    update(isNaN(num) ? min : num);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
      <TextField
        type="number"
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        inputProps={{ min }}
        size="small"
        label="Hotel budget"
        InputProps={{
          startAdornment: <InputAdornment position="start">$</InputAdornment>,
        }}
        sx={{ backgroundColor: 'var(--cream-light)', borderRadius: '8px' }}
      />

      {/* Quick-add buttons */}
      <Box sx={{ display: 'flex', gap: '6px' }}>
        {QUICK_STEPS.map((step) => (
          <Button
            key={step}
            size="small"
            variant="outlined"
            onClick={() => update((parseInt(value, 10) || min) + step)}
            sx={{
              flex: 1,
              fontSize: '0.72rem',
              fontWeight: 600,
              padding: '3px 0',
              borderColor: 'var(--cream-dark)',
              color: 'var(--bark-main)',
              backgroundColor: 'var(--cream-light)',
              borderRadius: '8px',
              minWidth: 0,
              textTransform: 'none',
              '&:hover': {
                borderColor: 'var(--bark-main)',
                backgroundColor: 'var(--cream-dark)',
              },
            }}
          >
            +${step}
          </Button>
        ))}
        <Button
          size="small"
          variant="outlined"
          onClick={() => update(min)}
          sx={{
            flex: 1,
            fontSize: '0.72rem',
            fontWeight: 600,
            padding: '3px 0',
            borderColor: 'var(--cream-dark)',
            color: 'var(--sand-main)',
            backgroundColor: 'var(--cream-light)',
            borderRadius: '8px',
            minWidth: 0,
            textTransform: 'none',
            '&:hover': {
              borderColor: 'var(--sand-main)',
              backgroundColor: 'var(--cream-dark)',
            },
          }}
        >
          Reset
        </Button>
      </Box>
    </Box>
  );
};

BudgetSlider.propTypes = {
  UserChatData: PropTypes.object,
  handleKeyDown: PropTypes.func,
  onValueChange: PropTypes.func,
};

export default BudgetSlider;
