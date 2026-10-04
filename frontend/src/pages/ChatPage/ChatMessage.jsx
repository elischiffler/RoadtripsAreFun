import { Box, Typography } from '@mui/material';
import PropTypes from 'prop-types';

export default function ChatMessage({ message, pendingLocationFields = [] }) {
  const presentation = message.sender === 'bot' ? message.presentation : null;
  const isList = (items) => Array.isArray(items) && items.every((item) => typeof item === 'string');
  if (
    !presentation ||
    typeof presentation.title !== 'string' ||
    !['updated', 'needed', 'notes'].every((key) => isList(presentation[key])) ||
    (presentation.introduction !== undefined && typeof presentation.introduction !== 'string') ||
    (presentation.questions !== undefined && !isList(presentation.questions))
  ) {
    return <Typography variant="body1">{message.text}</Typography>;
  }
  // Active confirmation controls already explain these requests. Keep the saved
  // receipt intact and hide only its matching location rows in the current reply.
  const locationLabels = {
    start_address: 'Starting location:',
    destination_address: 'Destination:',
  };
  const needed = presentation.needed.filter(
    (item) => !pendingLocationFields.some((field) => item.startsWith(locationLabels[field]))
  );
  if (
    !presentation.introduction &&
    !presentation.updated.length &&
    !needed.length &&
    !presentation.questions?.length &&
    !presentation.notes.length
  ) {
    return null;
  }
  return (
    <Box sx={{ overflowWrap: 'anywhere', minWidth: 0 }}>
      {presentation.introduction && (
        <Typography variant="body1" sx={{ mb: 1.5 }}>
          {presentation.introduction}
        </Typography>
      )}
      {[
        [presentation.title, presentation.updated],
        ['Still needed', needed],
        ['Questions', presentation.questions || []],
      ].map(([title, items]) =>
        items.length ? (
          <Box component="section" aria-label={title} key={title} sx={{ mb: 1.5 }}>
            <Typography component="h3" variant="body1" sx={{ fontWeight: 600 }}>
              {title}
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {items.map((item, index) => (
                <Typography component="li" variant="body1" key={index} sx={{ mt: 0.5 }}>
                  {item}
                </Typography>
              ))}
            </Box>
          </Box>
        ) : null
      )}
      {presentation.notes.map((note, index) => (
        <Typography key={index} variant="body1" sx={{ mt: 1 }}>
          {note}
        </Typography>
      ))}
    </Box>
  );
}

ChatMessage.propTypes = {
  message: PropTypes.shape({
    text: PropTypes.string,
    sender: PropTypes.string,
    presentation: PropTypes.object,
  }).isRequired,
  pendingLocationFields: PropTypes.arrayOf(PropTypes.string),
};
