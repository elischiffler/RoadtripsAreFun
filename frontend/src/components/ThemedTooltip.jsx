import { Tooltip, tooltipClasses } from '@mui/material';
import { styled } from '@mui/material/styles';

/**
 * ThemedTooltip — matches the earthy adventure palette.
 *
 * Cream-light background, bark-brown text, sand border, soft shadow.
 * Arrow inherits the same fill so it blends seamlessly.
 */
const ThemedTooltip = styled(({ className, ...props }) => (
  <Tooltip {...props} classes={{ popper: className }} />
))(({ theme }) => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: theme.palette.cream?.light ?? '#FBF8F3',
    color: theme.palette.bark?.main ?? '#7A5C44',
    border: `1px solid ${theme.palette.sand?.main ?? '#C4A882'}`,
    borderRadius: '8px',
    fontSize: '11px',
    fontFamily: "'Inter', sans-serif",
    fontWeight: 500,
    letterSpacing: '0.01em',
    padding: '6px 10px',
    boxShadow: '0 4px 12px rgba(58, 42, 26, 0.12)',
    maxWidth: 180,
  },
  [`& .${tooltipClasses.arrow}`]: {
    color: theme.palette.cream?.light ?? '#FBF8F3',
    '&::before': {
      border: `1px solid ${theme.palette.sand?.main ?? '#C4A882'}`,
    },
  },
}));

export default ThemedTooltip;
