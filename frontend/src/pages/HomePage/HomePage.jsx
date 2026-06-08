import { Box, Button, Typography } from '@mui/material';
import { Link, useNavigate } from 'react-router-dom';
import LogoButton from '../../components/LogoButton';
import RouteIcon from '@mui/icons-material/Route';
import SpinningWheelChip from '../../components/SpinningWheelChip';
import HotelChip from '../../components/HotelChip';
import ClockChip from '../../components/ClockChip';
import { isAuthenticated } from '../../services/authService';
import './HomePage.css';

export default function HomePage() {
  const navigate = useNavigate();
  const authenticated = isAuthenticated();

  const handleGetStartedClick = () => {
    navigate(authenticated ? '/chat' : '/login');
  };

  const handleLogout = () => {
    sessionStorage.removeItem('accessToken');
    sessionStorage.removeItem('idToken');
    sessionStorage.removeItem('refreshToken');
    navigate('/');
  };

  return (
    <Box className="home-page">
      {/* ── Navbar ── */}
      <Box className="navbar">
        <LogoButton />
        <Box className="navbar-actions">
          {authenticated ? (
            <>
              <Button
                variant="outlined"
                onClick={() => navigate('/chat')}
                className="nav-btn nav-btn--outline"
              >
                Open App
              </Button>
              <Button variant="contained" onClick={handleLogout} className="nav-btn nav-btn--solid">
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outlined"
                component={Link}
                to="/login"
                className="nav-btn nav-btn--outline"
              >
                Login
              </Button>
              <Button
                variant="contained"
                component={Link}
                to="/signup"
                className="nav-btn nav-btn--solid"
              >
                Sign Up
              </Button>
            </>
          )}
        </Box>
      </Box>

      {/* ── Main ── */}
      <Box className="main-panel">
        <Typography variant="h1" className="hero-title">
          RoadtripsAreFun
        </Typography>

        <Button
          variant="contained"
          onClick={handleGetStartedClick}
          className="hero-cta"
          size="large"
        >
          Start Planning
        </Button>

        {/* ── Feature chips ── */}
        <Box className="chip-row">
          <SpinningWheelChip label="Route generation" icon={<RouteIcon fontSize="small" />} />
          <HotelChip label="Hotel finder" />
          <ClockChip label="Itinerary builder" />
        </Box>
      </Box>
    </Box>
  );
}
