import { useEffect, useId, useState } from 'react';
import PropTypes from 'prop-types';
import { QuestionGroup } from './Layout';

export function ActionButton({
  variant = 'primary',
  type = 'button',
  className = '',
  children,
  ...props
}) {
  return (
    <button {...props} type={type} className={`rt-button rt-button--${variant} ${className}`}>
      {children}
    </button>
  );
}
ActionButton.propTypes = {
  variant: PropTypes.oneOf(['primary', 'secondary']),
  type: PropTypes.oneOf(['button', 'submit', 'reset']),
  className: PropTypes.string,
  children: PropTypes.node,
};

/** Native single-line input; callers own values, validation, and submission. */
export function Field({ id, label, hint, error, className = '', ...props }) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy = [props['aria-describedby'], hint ? hintId : null, error ? errorId : null]
    .filter(Boolean)
    .join(' ');
  return (
    <div className="rt-field">
      <label className="rt-field__label" htmlFor={inputId}>
        {label}
      </label>
      <input
        {...props}
        id={inputId}
        className={`rt-input ${className}`}
        aria-describedby={describedBy || undefined}
        aria-invalid={error ? true : props['aria-invalid']}
      />
      {hint && (
        <p id={hintId} className="rt-caption">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="rt-caption rt-field__error">
          {error}
        </p>
      )}
    </div>
  );
}
Field.propTypes = {
  id: PropTypes.string,
  label: PropTypes.string.isRequired,
  hint: PropTypes.string,
  error: PropTypes.string,
  className: PropTypes.string,
  'aria-describedby': PropTypes.string,
  'aria-invalid': PropTypes.oneOfType([PropTypes.bool, PropTypes.string]),
};

const expandedAmountLimit = (value) =>
  value > Number.MAX_VALUE / 2 ? Number.MAX_VALUE : value * 2;

/** Continuous native slider with explicit tap actions; stored amounts are never quantized. */
export function AmountControl({
  id,
  label,
  value,
  onChange,
  initialMax = 100,
  disabled = false,
  describedBy,
}) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const [upperBound, setUpperBound] = useState(() =>
    Math.max(initialMax, expandedAmountLimit(value), Number.MIN_VALUE)
  );
  const [announcement, setAnnouncement] = useState('');
  // Expand for externally restored amounts too, without ever writing to the caller.
  // Bounds do not shrink during a drag, so the thumb follows the pointer directly.
  useEffect(() => {
    setUpperBound((previous) => (value > previous ? expandedAmountLimit(value) : previous));
  }, [value]);
  const maximum = Math.max(upperBound, value);
  const increment = Math.max(Number.MIN_VALUE, 10 ** (Math.floor(Math.log10(maximum)) - 2));
  const change = (next, announce = false) => {
    if (!disabled && Number.isFinite(next) && next >= 0) {
      onChange(next);
      setAnnouncement(announce ? `${label}: ${next} relative amount` : '');
    }
  };
  const increase = () =>
    change(value > Number.MAX_VALUE - increment ? Number.MAX_VALUE : value + increment, true);
  return (
    <div className="rt-amount">
      <div className="rt-amount__heading">
        <label className="rt-field__label" htmlFor={inputId}>
          {label}
        </label>
        <output htmlFor={inputId} className="rt-caption" title={String(value)} aria-hidden="true">
          {Number(value.toPrecision(4)).toString()}
        </output>
      </div>
      <div className="rt-amount__controls">
        <ActionButton
          variant="secondary"
          className="rt-amount__step"
          aria-label={`Less ${label}`}
          aria-controls={inputId}
          disabled={disabled || value === 0}
          onClick={() => change(Math.max(0, value - increment), true)}
        >
          <span aria-hidden="true">−</span>
        </ActionButton>
        <input
          id={inputId}
          className="rt-amount__range"
          type="range"
          min="0"
          max={maximum}
          step="any"
          value={value}
          onChange={(event) => change(Number(event.target.value))}
          disabled={disabled}
          aria-valuetext={`${value} relative amount`}
          aria-describedby={describedBy}
        />
        <ActionButton
          variant="secondary"
          className="rt-amount__step"
          aria-label={`More ${label}`}
          aria-controls={inputId}
          disabled={disabled || value === Number.MAX_VALUE}
          onClick={increase}
        >
          <span aria-hidden="true">+</span>
        </ActionButton>
      </div>
      <span className="rt-visually-hidden" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </span>
    </div>
  );
}
AmountControl.propTypes = {
  id: PropTypes.string,
  label: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  initialMax: PropTypes.number,
  disabled: PropTypes.bool,
  describedBy: PropTypes.string,
};

export function ChoiceGroup({
  legend,
  description,
  name,
  value,
  onChange,
  options,
  disabled = false,
}) {
  const generatedName = useId();
  return (
    <QuestionGroup legend={legend} description={description} disabled={disabled}>
      <div className="rt-choices">
        {options.map((option) => (
          <label key={option.value} className="rt-choice">
            <input
              type="radio"
              name={name || generatedName}
              value={option.value}
              checked={value === option.value}
              onChange={() => {
                if (!disabled && !option.disabled) onChange(option.value);
              }}
              disabled={disabled || option.disabled}
            />
            <span className="rt-choice__body">
              <span className="rt-field__label">{option.label}</span>
              {option.description && <span className="rt-caption">{option.description}</span>}
            </span>
          </label>
        ))}
      </div>
    </QuestionGroup>
  );
}
ChoiceGroup.propTypes = {
  legend: PropTypes.string.isRequired,
  description: PropTypes.string,
  name: PropTypes.string,
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      description: PropTypes.string,
      disabled: PropTypes.bool,
    })
  ).isRequired,
  disabled: PropTypes.bool,
};
