import { Button, Box, Typography } from "@mui/material";
import KeyboardReturnIcon from "@mui/icons-material/KeyboardReturn";
import { Link } from "react-router-dom";
import './ButtonStyles.css'; 

const ChatButton = () => {
  return (
    <Link to="/chat" className="link">
      <Button
        variant="contained"
        className="button"
      >
        <Box className="button-content">
          <KeyboardReturnIcon className="button-icon" />
          <Typography variant="body1" className="typography">
            Chat
          </Typography>
        </Box>
      </Button>
    </Link>
  );
};

export default ChatButton;