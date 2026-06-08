import { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Typography, TextField, InputAdornment, IconButton } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PropTypes from 'prop-types';
import './TripSearch.css';

// Single-dot progress light — color shifts from sand → amber as trip advances
const ProgressLight = ({ step }) => (
  <Box className={`ts-light ts-light--step-${step}`} title={`Progress: ${step} / 5`} />
);

ProgressLight.propTypes = { step: PropTypes.number.isRequired };

const TripSearch = ({
  chats,
  onSelect,
  onDelete,
  onClose,
  selectedChatId,
  getChatInfo,
  isFetchingChats,
}) => {
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const results = chats.filter((chat) => {
    const dest = chat.title.startsWith('Trip to ')
      ? chat.title.replace('Trip to ', '')
      : chat.title;
    return dest.toLowerCase().includes(query.toLowerCase());
  });

  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && results[activeIdx]) {
        onSelect(results[activeIdx]);
      } else if (e.key === 'Escape') {
        onClose();
      }
    },
    [results, activeIdx, onSelect, onClose]
  );

  return (
    <Box className="ts-backdrop" onClick={onClose}>
      <Box className="ts-modal" onClick={(e) => e.stopPropagation()}>
        <TextField
          inputRef={inputRef}
          fullWidth
          placeholder="Search trips…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          variant="outlined"
          className="ts-input"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon className="ts-search-icon" />
              </InputAdornment>
            ),
          }}
        />

        <Box className="ts-results">
          {results.length === 0 && !isFetchingChats ? (
            <Typography className="ts-empty">No trips found</Typography>
          ) : (
            results.map((chat, idx) => {
              const dest = chat.title.startsWith('Trip to ')
                ? chat.title.replace('Trip to ', '')
                : chat.title;
              const info = getChatInfo ? getChatInfo(chat.id) : { step: 1 };
              const { step, startCity, endCity } = info;
              const isCurrentTrip = chat.id === selectedChatId;

              return (
                <Box
                  key={chat.id}
                  className={`ts-result${idx === activeIdx ? ' ts-result--active' : ''}${isCurrentTrip ? ' ts-result--current' : ''}`}
                  onClick={() => onSelect(chat)}
                  onMouseEnter={() => setActiveIdx(idx)}
                >
                  <DirectionsCarIcon className="ts-result-icon" />

                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    {/* Title row */}
                    <Box className="ts-title-row">
                      <Typography className="ts-result-dest">{dest}</Typography>
                      {isCurrentTrip && <Box className="ts-current-dot" title="Current trip" />}
                    </Box>

                    {/* Route row */}
                    {(startCity || endCity) && (
                      <Box className="ts-route-row">
                        <Typography className="ts-city">{startCity ?? '…'}</Typography>
                        <ArrowForwardIcon className="ts-arrow" />
                        <Typography className="ts-city">{endCity ?? '…'}</Typography>
                      </Box>
                    )}
                  </Box>

                  {/* Progress light — direct child of ts-result so it's vertically centred */}
                  <ProgressLight step={step} />

                  <IconButton
                    size="small"
                    className="ts-delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(chat.id);
                    }}
                    aria-label={`Delete ${dest}`}
                  >
                    <DeleteOutlineIcon className="ts-delete-icon" />
                  </IconButton>
                </Box>
              );
            })
          )}
          {isFetchingChats && (
            <Box className="ts-loading-row ts-loading-row--footer">
              <Typography className="ts-loading-text">Loading previous trips…</Typography>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
};

TripSearch.propTypes = {
  chats: PropTypes.array.isRequired,
  onSelect: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  selectedChatId: PropTypes.number,
  getChatInfo: PropTypes.func,
  isFetchingChats: PropTypes.bool,
};

export default TripSearch;
