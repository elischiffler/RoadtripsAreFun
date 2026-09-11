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
// Default algorithm when nothing has been picked yet.
const DEFAULT_ALGORITHM = 'greedy';

/**
 * Persist the selected routing algorithm, tolerating a failing localStorage
 * (private mode, quota, storage disabled). A write failure is non-fatal: the
 * picker keeps working in-memory, and getFinalRoute() still falls back to the
 * backend default when nothing is stored.
 */
function writeRoutingAlgorithm(algo) {
  try {
    localStorage.setItem(ROUTING_ALGORITHM_KEY, algo);
  } catch (err) {
    console.warn('Could not persist routing algorithm to localStorage:', err);
  }
}

export default function AlgorithmSettings() {
  const [anchorEl, setAnchorEl] = useState(null);
  const [algorithms, setAlgorithms] = useState([]);
  const [selected, setSelected] = useState(getRoutingAlgorithm() || DEFAULT_ALGORITHM);
  const open = Boolean(anchorEl);

  useEffect(() => {
    // Persist the default on first load so what the UI shows matches what gets
    // sent (getFinalRoute reads localStorage).
    if (!getRoutingAlgorithm()) {
      writeRoutingAlgorithm(DEFAULT_ALGORITHM);
    }
  }, []);

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
    writeRoutingAlgorithm(algo);
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

        {algorithms.map((algo) => (
          <MenuItem key={algo} onClick={() => choose(algo)} sx={{ fontSize: '0.85rem' }}>
            {selected === algo && <CheckIcon fontSize="small" sx={{ mr: 1 }} />}
            <span style={{ marginLeft: selected === algo ? 0 : 28 }}>{algo}</span>
          </MenuItem>
        ))}

        <Box sx={{ px: 2, py: 1 }}>
          <Chip
            label={`active: ${selected}`}
            size="small"
            sx={{ backgroundColor: 'var(--amber-light)', fontSize: '0.7rem' }}
          />
        </Box>
      </Menu>
    </>
  );
}
