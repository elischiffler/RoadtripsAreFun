import { useState } from 'react';
import PropTypes from 'prop-types';
import { Tooltip } from '@mui/material';

/** The same short definition works with pointer hover, keyboard focus or a tap. */
export default function HelpTip({ label, children }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip
      title={children}
      describeChild
      arrow
      open={open}
      onOpen={() => setOpen(true)}
      onClose={() => setOpen(false)}
    >
      <button
        type="button"
        className="lab-help"
        aria-label={`About ${label}`}
        onClick={() => setOpen(true)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
      >
        ?
      </button>
    </Tooltip>
  );
}

HelpTip.propTypes = { label: PropTypes.string.isRequired, children: PropTypes.node.isRequired };
