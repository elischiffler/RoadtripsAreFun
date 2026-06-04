import { Button, Box, Typography, Tooltip } from '@mui/material';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import { Link } from 'react-router-dom';
import PropTypes from 'prop-types';

// ItineraryButton component that conditionally renders a link to the itinerary page
const ItineraryButton = ({ itinerary }) => {
  const button = (
    <Button
      variant="contained"
      color="green"
      startIcon={<FormatListBulletedIcon className="button-icon" />} // Add itinerary icon to the button
      className="button"
      disabled={!itinerary} // Disable button if no itinerary
    >
      <Box className="button-content">
        <Typography variant="body1" className="typography">
          Itinerary
        </Typography>
      </Box>
    </Button>
  );

  return (
    <Link
      to={itinerary ? '/itinerary' : '#'} // Prevent navigation if itinerary is not provided
      className="link"
      onClick={(e) => {
        if (!itinerary) e.preventDefault(); // Disable link if no itinerary
      }}
    >
      {/* Conditionally wrap the button in a Tooltip if the button is disabled */}
      {!itinerary ? (
        <Tooltip title="Please answer the questions first" placement="right" arrow>
          <span>{button}</span>
        </Tooltip>
      ) : (
        button
      )}
    </Link>
  );
};

ItineraryButton.propTypes = {
  itinerary: PropTypes.array,
};

export default ItineraryButton;
