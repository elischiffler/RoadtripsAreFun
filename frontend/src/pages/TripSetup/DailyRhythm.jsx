import { useId } from 'react';
import PropTypes from 'prop-types';
import { ActionButton } from '../../design';
import { dailyScheduleFromRhythm, DEFAULT_DAILY_RHYTHM, hourLabel } from './dailyRhythm';
import './DailyRhythm.css';

const HANDLES = [
  ['driveStart', 'Start driving'],
  ['driveEnd', 'Stop driving'],
  ['sleepStart', 'Start sleep'],
  ['sleepEnd', 'Wake up'],
];

export default function DailyRhythm({ value, onChange, disabled = false, error }) {
  const id = useId();
  const rhythm = value ?? DEFAULT_DAILY_RHYTHM;
  let slots;
  let issue = error;
  try {
    slots = dailyScheduleFromRhythm(rhythm).slots;
  } catch (failure) {
    issue ||= failure.message;
  }
  return (
    <section className="setup-rhythm" aria-labelledby={`${id}-heading`}>
      <header>
        <h3 id={`${id}-heading`} className="rt-title">
          Your 24 hours
        </h3>
        <p className="rt-caption">Driving time can also include stops and meals.</p>
      </header>
      <div
        className="setup-rhythm-bar"
        role="img"
        aria-label={`Drive ${hourLabel(rhythm.driveStart)} to ${hourLabel(rhythm.driveEnd)}; sleep ${hourLabel(rhythm.sleepStart)} to ${hourLabel(rhythm.sleepEnd)}. Other hours are rest.`}
      >
        {(slots ?? Array(24).fill('rest')).map((slot, hour) => (
          <span key={hour} data-period={slot} title={`${hourLabel(hour)} · ${slot}`} />
        ))}
      </div>
      <div className="setup-rhythm-scale rt-caption" aria-hidden="true">
        <span>00</span>
        <span>06</span>
        <span>12</span>
        <span>18</span>
        <span>24</span>
      </div>
      <div className="setup-rhythm-legend rt-caption">
        <span data-period="drive">Drive / explore</span>
        <span data-period="rest">Rest</span>
        <span data-period="sleep">Sleep</span>
      </div>
      {!value && (
        <p className="rt-caption">Existing timing stays in use until you adjust this rhythm.</p>
      )}
      <div className="setup-rhythm-controls">
        {HANDLES.map(([key, label]) => (
          <label key={key} className="setup-rhythm-handle">
            <span className="rt-field__label">
              {label} <strong>{hourLabel(rhythm[key])}</strong>
            </span>
            <input
              aria-label={label}
              className="rt-amount__range"
              type="range"
              min="0"
              max="23"
              step="1"
              value={rhythm[key]}
              disabled={disabled}
              aria-valuetext={hourLabel(rhythm[key])}
              aria-describedby={issue ? `${id}-error` : undefined}
              aria-invalid={issue ? true : undefined}
              onChange={(event) => onChange({ ...rhythm, [key]: Number(event.target.value) })}
            />
          </label>
        ))}
      </div>
      {issue && (
        <p id={`${id}-error`} className="setup-error" role="status">
          {issue}
        </p>
      )}
      {!value && (
        <ActionButton
          variant="secondary"
          disabled={disabled}
          onClick={() => onChange({ ...DEFAULT_DAILY_RHYTHM })}
        >
          Use this rhythm
        </ActionButton>
      )}
    </section>
  );
}
DailyRhythm.propTypes = {
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  error: PropTypes.string,
};
