import { useState, useContext } from 'react';
import { Box, Button, Typography, Menu, MenuItem, Divider } from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import LogoButton from './LogoButton';
import LogoutIcon from '@mui/icons-material/Logout';
import { UserDataContext } from '../states/UserDataContext';
import { isAuthenticated } from '../services/authService';
import './GlobalHeader.css';
import { signOut } from '../services/session';
import { useSessionStatus } from '../services/useSessionStatus';

const HIDDEN_ON = ['/login', '/signup', '/studio'];

export default function GlobalHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  useSessionStatus();
  const authed = isAuthenticated();
  const { clearUserData } = useContext(UserDataContext);

  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleAvatarClick = (e) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handleSignOut = () => {
    handleClose();
    signOut();
    clearUserData();
    navigate('/');
  };

  if (HIDDEN_ON.includes(location.pathname)) return null;

  const onMapPage = location.pathname === '/map';
  const logoProgress = onMapPage || location.pathname === '/itinerary' ? 1 : 0;

  return (
    <Box className={`global-header${onMapPage ? ' global-header--transparent' : ''}`}>
      <LogoButton progress={logoProgress} />

      <Box className="global-header-right">
        <Button component={Link} to="/plan" sx={{ color: 'text.primary', px: 1 }}>
          Plan a trip
        </Button>
        <Button component={Link} to="/trips" sx={{ color: 'text.primary', px: 1 }}>
          Saved trips
        </Button>
        <Button component={Link} to="/studio" sx={{ color: 'text.primary', px: 1 }}>
          AI Studio
        </Button>
        {authed ? (
          <>
            <Box
              component="button"
              type="button"
              aria-label="Account menu"
              className="avatar-placeholder"
              onClick={handleAvatarClick}
              aria-controls={open ? 'profile-menu' : undefined}
              aria-haspopup="true"
              aria-expanded={open ? 'true' : undefined}
            >
              <Typography className="avatar-initials">U</Typography>
            </Box>

            <Menu
              id="profile-menu"
              anchorEl={anchorEl}
              open={open}
              onClose={handleClose}
              onClick={handleClose}
              slotProps={{
                paper: {
                  className: 'profile-menu-paper',
                  elevation: 3,
                  sx: {
                    backgroundColor: 'var(--cream-light)',
                    border: '1px solid var(--cream-dark)',
                    borderRadius: '10px',
                  },
                },
              }}
              transformOrigin={{ horizontal: 'right', vertical: 'top' }}
              anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
              <Box className="profile-menu-header">
                <Typography className="profile-menu-label">Account</Typography>
              </Box>
              <Divider sx={{ borderColor: 'var(--cream-dark)' }} />
              <MenuItem onClick={handleSignOut} className="profile-menu-item">
                <LogoutIcon className="profile-menu-icon" />
                Sign out
              </MenuItem>
            </Menu>
          </>
        ) : (
          <Button
            variant="contained"
            component={Link}
            to="/login"
            sx={{
              backgroundColor: 'var(--amber-main)',
              color: '#1e1208',
              fontSize: '0.8rem',
              fontWeight: 600,
              padding: '6px 18px',
              borderRadius: '8px',
              boxShadow: 'none',
              '&:hover': {
                backgroundColor: 'var(--amber-light)',
                boxShadow: 'none',
              },
            }}
          >
            Login
          </Button>
        )}
      </Box>
    </Box>
  );
}
