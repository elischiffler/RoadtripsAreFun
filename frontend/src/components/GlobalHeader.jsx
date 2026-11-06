import { useState, useContext } from 'react';
import { Box, Button, Typography, Menu, MenuItem, Divider } from '@mui/material';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import LogoButton from './LogoButton';
import LogoutIcon from '@mui/icons-material/Logout';
import { UserDataContext } from '../states/UserDataContext';
import { isAuthenticated } from '../services/authService';
import '../design/index.css';
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

  if (HIDDEN_ON.includes(location.pathname) || location.pathname.startsWith('/studio/'))
    return null;

  const onMapPage = location.pathname === '/map';

  return (
    <Box className={`rt-design global-header${onMapPage ? ' global-header--transparent' : ''}`}>
      <LogoButton />

      <Box className="global-header-right">
        <Button component={Link} to="/plan" aria-label="Plan a trip" className="header-nav-link">
          <span className="header-label-wide">Plan a trip</span>
          <span className="header-label-compact" aria-hidden="true">
            Plan
          </span>
        </Button>
        <Button component={Link} to="/trips" aria-label="Saved trips" className="header-nav-link">
          <span className="header-label-wide">Saved trips</span>
          <span className="header-label-compact" aria-hidden="true">
            Trips
          </span>
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
                  className: 'rt-design profile-menu-paper',
                  elevation: 3,
                },
              }}
              transformOrigin={{ horizontal: 'right', vertical: 'top' }}
              anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
              <Box className="profile-menu-header">
                <Typography className="profile-menu-label">Account</Typography>
              </Box>
              <Divider />
              <MenuItem component={Link} to="/settings" className="profile-menu-item">
                Settings
              </MenuItem>
              <MenuItem onClick={handleSignOut} className="profile-menu-item">
                <LogoutIcon className="profile-menu-icon" />
                Sign out
              </MenuItem>
            </Menu>
          </>
        ) : (
          <Button variant="contained" component={Link} to="/login" className="header-login">
            Login
          </Button>
        )}
      </Box>
    </Box>
  );
}
