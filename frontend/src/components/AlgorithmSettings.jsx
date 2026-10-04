import { useState } from 'react';
import { Box, IconButton, Menu, MenuItem, Typography, Divider, Chip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import CheckIcon from '@mui/icons-material/Check';
import {
  useRoutingSettings,
  getRoutingAlgorithm,
  chooseRoutingAlgorithm,
} from '../services/routingSettings';

/**
 * Dev-mode routing-algorithm picker.
 *
 * A gear button that opens a small popup listing the routing algorithms the
 * backend has registered for a verified owner. Selection lasts for this session.
 *
 * This is a developer/demo tool for switching among current and future CP-SAT variants.
 */
export default function AlgorithmSettings() {
  const [anchorEl, setAnchorEl] = useState(null);
  const { canSelect, algorithms, defaultAlgorithm } = useRoutingSettings();
  const selected = getRoutingAlgorithm() || defaultAlgorithm;
  const open = Boolean(anchorEl);

  const choose = (algo) => {
    chooseRoutingAlgorithm(algo);
    setAnchorEl(null);
  };

  if (!canSelect) return null;

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
