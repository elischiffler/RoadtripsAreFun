import { useState, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import PropTypes from 'prop-types';
import './InputStops.css';

const OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

/**
 * StopSlider — a horizontally scrolling pill carousel.
 * Tapping a pill selects it and calls onSelect(n) to advance the workflow.
 */
const StopSlider = ({ onSelect }) => {
  const [selected, setSelected] = useState(1);
  const scrollRef = useRef(null);

  const handleSelect = (n) => {
    setSelected(n);
    if (onSelect) onSelect(n);
  };

  return (
    <Box className="stop-carousel-wrapper">
      {/* Fade masks */}
      <Box className="stop-fade stop-fade--left" />
      <Box className="stop-fade stop-fade--right" />

      <Box className="stop-carousel" ref={scrollRef}>
        {OPTIONS.map((n) => (
          <Box
            key={n}
            className={`stop-pill${selected === n ? ' stop-pill--selected' : ''}`}
            onClick={() => handleSelect(n)}
            role="button"
            aria-label={`${n} stop${n !== 1 ? 's' : ''}`}
            aria-pressed={selected === n}
          >
            <Typography className="stop-pill-label">{n}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

StopSlider.propTypes = {
  onSelect: PropTypes.func,
};

export default StopSlider;
