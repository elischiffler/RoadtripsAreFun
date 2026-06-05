import { useState, useRef, useEffect } from 'react';
import { Box, TextField, IconButton, CircularProgress } from '@mui/material';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import PropTypes from 'prop-types';
import ThemedTooltip from '../../components/ThemedTooltip';
import './ChatPage.css';

/**
 * LocationInput — a single-field address bar with a "use my location" button.
 *
 * Props:
 *   placeholder  {string}   – field placeholder text
 *   onSubmit     {fn}       – called with the text string when the user submits
 *   onGeolocate  {fn}       – called with [lat, lon] when the location button resolves
 *   disabled     {boolean}  – disables input while validating
 */
const LocationInput = ({ placeholder, onSubmit, onGeolocate, disabled }) => {
  const [value, setValue] = useState('');
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (value.trim()) {
        onSubmit(value.trim());
        setValue('');
      }
    }
  };

  const handleGeolocate = () => {
    if (!navigator.geolocation) return;
    setGeoLoading(true);
    setGeoError(false);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoLoading(false);
        onGeolocate([pos.coords.latitude, pos.coords.longitude]);
      },
      () => {
        setGeoLoading(false);
        setGeoError(true);
      }
    );
  };

  return (
    <Box className="location-input-row">
      <TextField
        inputRef={inputRef}
        className="location-input-field"
        placeholder={placeholder || 'Enter a city, address, or zip code…'}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        fullWidth
        autoComplete="off"
        size="small"
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: '10px',
            backgroundColor: 'var(--cream-light)',
          },
        }}
      />
      <ThemedTooltip
        title={geoError ? 'Location access denied' : 'Use my current location'}
        placement="top"
        arrow
      >
        <span>
          <IconButton
            className={`geo-btn${geoError ? ' geo-btn--error' : ''}`}
            onClick={handleGeolocate}
            disabled={disabled || geoLoading}
            aria-label="Use my location"
            size="small"
          >
            {geoLoading ? (
              <CircularProgress size={18} sx={{ color: 'var(--sand-main)' }} />
            ) : (
              <MyLocationIcon
                sx={{
                  fontSize: 20,
                  color: geoError ? '#b42828' : 'var(--amber-main)',
                }}
              />
            )}
          </IconButton>
        </span>
      </ThemedTooltip>
    </Box>
  );
};

LocationInput.propTypes = {
  placeholder: PropTypes.string,
  onSubmit: PropTypes.func.isRequired,
  onGeolocate: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};

export default LocationInput;
