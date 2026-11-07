import PropTypes from 'prop-types';
import { ActionButton, Field } from '../../design';
import { MAX_SETUP_ROOMS } from './setupModel';

export default function HotelQuestions({ draft, onChange, errors = {}, disabled = false }) {
  const room = (index, key, value) =>
    onChange({
      ...draft,
      rooms: draft.rooms.map((item, position) =>
        position === index ? { ...item, [key]: value } : item
      ),
    });
  return (
    <fieldset className="setup-fields" disabled={disabled}>
      <legend className="rt-title">If you need a stay</legend>
      <p className="rt-caption">{draft.travelers} people · no hotel is booked.</p>
      <div id="hotel-rooms" className="rt-stack">
        {draft.rooms.map((item, index) => (
          <fieldset className="setup-room" key={index}>
            <legend>Room {index + 1}</legend>
            <div className="setup-grid">
              <Field
                id={`hotel-room-${index}-adults`}
                label={`Adults in room ${index + 1}`}
                type="number"
                min="1"
                max="6"
                step="1"
                value={item.adults}
                onChange={(event) => room(index, 'adults', event.target.value)}
              />
              <Field
                id={`hotel-room-${index}-children`}
                label={`Child ages in room ${index + 1}`}
                hint="Optional, comma-separated."
                value={item.children}
                onChange={(event) => room(index, 'children', event.target.value)}
              />
            </div>
            {draft.rooms.length > 1 && (
              <ActionButton
                variant="secondary"
                onClick={() =>
                  onChange({
                    ...draft,
                    rooms: draft.rooms.filter((_, position) => position !== index),
                  })
                }
              >
                Remove room {index + 1}
              </ActionButton>
            )}
          </fieldset>
        ))}
      </div>
      {errors.rooms && (
        <p role="status" className="setup-error">
          {errors.rooms}
        </p>
      )}
      <ActionButton
        variant="secondary"
        disabled={disabled || draft.rooms.length >= MAX_SETUP_ROOMS}
        onClick={() =>
          onChange({ ...draft, rooms: [...draft.rooms, { adults: '1', children: '' }] })
        }
      >
        Add a room
      </ActionButton>
      <Field
        id="hotel-budget"
        label="Hotel target per room / night"
        type="number"
        min="0"
        step="any"
        value={draft.budget}
        error={errors.budget}
        onChange={(event) => onChange({ ...draft, budget: event.target.value })}
      />
    </fieldset>
  );
}
HotelQuestions.propTypes = {
  draft: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  errors: PropTypes.object,
  disabled: PropTypes.bool,
};
