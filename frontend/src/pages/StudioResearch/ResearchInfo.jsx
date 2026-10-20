import { useEffect, useId, useRef, useState } from 'react';
import PropTypes from 'prop-types';

export default function ResearchInfo({ label, children }) {
  const id = useId();
  const root = useRef(null);
  const [open, setOpen] = useState(false);
  const [above, setAbove] = useState(false);
  const show = () => {
    const rect = root.current?.getBoundingClientRect();
    setAbove(Boolean(rect && rect.bottom > window.innerHeight / 2));
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const dismiss = (event) => {
      if (!root.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', dismiss);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  return (
    <span
      className="research-info"
      ref={root}
      data-side={above ? 'above' : 'below'}
      onMouseEnter={show}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="research-info-button"
        aria-label={`About ${label}`}
        aria-describedby={open ? id : undefined}
        onClick={show}
        onFocus={show}
        onBlur={() => setOpen(false)}
      >
        <span aria-hidden="true">i</span>
      </button>
      {open && (
        <span className="research-tooltip" role="tooltip" id={id}>
          <span>{children}</span>
        </span>
      )}
    </span>
  );
}
ResearchInfo.propTypes = {
  label: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
};

export function ChartHeading({ title, unit, help, as: Tag = 'figcaption' }) {
  return (
    <Tag className="research-chart-heading">
      <span>
        {title}
        {unit && <small>{unit}</small>}
      </span>
      <ResearchInfo label={title}>{help}</ResearchInfo>
    </Tag>
  );
}
ChartHeading.propTypes = {
  title: PropTypes.string.isRequired,
  unit: PropTypes.string,
  help: PropTypes.node.isRequired,
  as: PropTypes.string,
};
