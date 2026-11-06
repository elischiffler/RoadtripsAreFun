import { useId } from 'react';
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
