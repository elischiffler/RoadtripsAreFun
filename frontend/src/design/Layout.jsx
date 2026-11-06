import { useId } from 'react';
import PropTypes from 'prop-types';

export function DesignFrame({ children, className = '', ...props }) {
  return (
    <div {...props} className={`rt-design ${className}`}>
      <div className="rt-design__content rt-stack">{children}</div>
    </div>
  );
}
DesignFrame.propTypes = { children: PropTypes.node, className: PropTypes.string };

/** A nonmodal surface in document flow; no focus trap or drag affordance. */
export function Sheet({ children, floating = false, className = '', ...props }) {
  return (
    <section
      {...props}
      className={`rt-sheet rt-stack ${floating ? 'rt-sheet--floating' : ''} ${className}`}
    >
      {children}
    </section>
  );
}
Sheet.propTypes = {
  children: PropTypes.node,
  floating: PropTypes.bool,
  className: PropTypes.string,
};

export function QuestionGroup({ legend, description, children, ...props }) {
  const descriptionId = useId();
  return (
    <fieldset
      {...props}
      className="rt-question-group"
      aria-describedby={
        [props['aria-describedby'], description ? descriptionId : null].filter(Boolean).join(' ') ||
        undefined
      }
    >
      <legend className="rt-title">{legend}</legend>
      {description && (
        <p id={descriptionId} className="rt-caption">
          {description}
        </p>
      )}
      {children}
    </fieldset>
  );
}
QuestionGroup.propTypes = {
  legend: PropTypes.string.isRequired,
  description: PropTypes.string,
  children: PropTypes.node,
  'aria-describedby': PropTypes.string,
};
