import { useState, useEffect } from 'react';
import axios from 'axios';
import { Box, IconButton, Menu, MenuItem, Typography, Divider, Chip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CheckIcon from '@mui/icons-material/Check';
import { ROUTING_ALGORITHM_KEY, getRoutingAlgorithm } from '../pages/ChatPage/getRoute';

/**
 * Dev-mode routing-algorithm picker.
 *
 * A gear button that opens a small popup listing the routing algorithms the
 * backend has registered (fetched from GET /algorithms). Selecting one stores it
 * in localStorage; getFinalRoute() then sends it as the `algorithm` field on the
 * next trip. "Default" clears the override so the backend chooses.
 *
 * This is a developer/demo tool — it doesn't change production behavior unless a
 * non-default algorithm is explicitly selected.
 */
export default function AlgorithmSettings() {
  const [anchorEl, setAnchorEl] = useState(null);
  const [algorithms, setAlgorithms] = useState([]);
  const [selected, setSelected] = useState(getRoutingAlgorithm());
  const open = Boolean(anchorEl);

  useEffect(() => {
    // Load the available algorithms once, when the popup is first opened.
    if (open && algorithms.length === 0) {
      axios
        .get(`${import.meta.env.VITE_BACKEND_SERVER}algorithms`)
        .then((res) => setAlgorithms(res.data.algorithms || []))
        .catch(() => setAlgorithms([]));
    }
  }, [open, algorithms.length]);

  const choose = (algo) => {
    if (algo) {
      localStorage.setItem(ROUTING_ALGORITHM_KEY, algo);
    } else {
      localStorage.removeItem(ROUTING_ALGORITHM_KEY);
    }
    setSelected(algo);
    setAnchorEl(null);
  };

  return (
    <>
      <IconButton
        onClick={(e) => setAnchorEl(e.currentTarget)}
        aria-label="routing algorithm settings"
        title="Dev: routing algorithm"
        size="small"
        sx={{ color: 'var(--amber-main)' }}
      >
        <SettingsIcon fontSize="small" />
      </IconButton>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={() => setAnchorEl(null)}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        slotProps={{
          paper: {
            sx: {
              backgroundColor: 'var(--cream-light)',
              border: '1px solid var(--cream-dark)',
              borderRadius: '10px',
              minWidth: 220,
            },
          },
        }}
      >
        <Box sx={{ px: 2, py: 1 }}>
          <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: 0.5 }}>
            DEV · ROUTING ALGORITHM
          </Typography>
          <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
            Applies to the next trip you plan.
          </Typography>
        </Box>
        <Divider sx={{ borderColor: 'var(--cream-dark)' }} />

        <MenuItem onClick={() => choose(null)} sx={{ fontSize: '0.85rem' }}>
          {selected === null && <CheckIcon fontSize="small" sx={{ mr: 1 }} />}
          <span style={{ marginLeft: selected === null ? 0 : 28 }}>Default (backend chooses)</span>
        </MenuItem>

        {algorithms.map((algo) => (
          <MenuItem key={algo} onClick={() => choose(algo)} sx={{ fontSize: '0.85rem' }}>
            {selected === algo && <CheckIcon fontSize="small" sx={{ mr: 1 }} />}
            <span style={{ marginLeft: selected === algo ? 0 : 28 }}>{algo}</span>
          </MenuItem>
        ))}

        {selected && (
          <Box sx={{ px: 2, py: 1 }}>
            <Chip
              label={`active: ${selected}`}
              size="small"
              sx={{ backgroundColor: 'var(--amber-light)', fontSize: '0.7rem' }}
            />
          </Box>
        )}
      </Menu>
    </>
  );
}
