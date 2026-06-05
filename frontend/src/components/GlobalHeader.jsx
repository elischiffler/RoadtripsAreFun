import { useState, useContext } from 'react';
import { Box, Button, Typography, Menu, MenuItem, Divider } from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import LogoButton from './LogoButton';
import LogoutIcon from '@mui/icons-material/Logout';
import { UserDataContext } from '../states/UserDataContext';
import './GlobalHeader.css';

const HIDDEN_ON = ['/login', '/signup'];

const isAuthenticated = () => !!sessionStorage.getItem('accessToken');

export default function GlobalHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const authed = isAuthenticated();
  const { currentStep } = useContext(UserDataContext);

  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleAvatarClick = (e) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handleSignOut = () => {
    handleClose();
    sessionStorage.removeItem('accessToken');
    sessionStorage.removeItem('idToken');
    sessionStorage.removeItem('refreshToken');
    navigate('/');
  };

  if (HIDDEN_ON.includes(location.pathname)) return null;

  const onChatPage = location.pathname === '/chat';
  const onItineraryPage = location.pathname === '/itinerary';
  const onMapPage = location.pathname === '/map';
  const chatProgress = Math.min((currentStep - 1) / 4, 1);
  // Animate from step 1 onwards; stop only when the trip is complete (step 5)
  const isDriving = onChatPage && currentStep < 5;

  // On the itinerary page the trip is fully planned — show the car at the end
  const logoProgress = onItineraryPage || onMapPage ? 1 : onChatPage ? chatProgress : 0;

  return (
    <Box className={`global-header${onMapPage ? ' global-header--transparent' : ''}`}>
      <LogoButton driving={isDriving} progress={logoProgress} />

      <Box className="global-header-right">
        {authed ? (
          <>
            <Box
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
          <Button variant="contained" component={Link} to="/login" className="header-login-btn">
            Login
          </Button>
        )}
      </Box>
    </Box>
  );
}
