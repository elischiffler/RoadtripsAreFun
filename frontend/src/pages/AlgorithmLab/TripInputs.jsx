import PropTypes from 'prop-types';
import HelpTip from './HelpTip';
import InterestsPie from './InterestsPie';

const title = (key) => key.replaceAll('_', ' ');

export default function TripInputs({ inputs, catalog, onChange, disabled }) {
  const set = (key, value) => onChange({ ...inputs, [key]: value });
  const policy = inputs.scheduling_policy;
  const setRoom = (index, room) =>
    set(
      'hotel_rooms',
      inputs.hotel_rooms.map((old, i) => (i === index ? room : old))
    );
  const numberField = (key, label, min, max) => (
    <label>
      {label}
      <input
        type="number"
        required
        min={min}
        max={max}
        value={inputs[key]}
        onChange={(e) => set(key, e.target.value === '' ? '' : Number(e.target.value))}
      />
    </label>
  );
  return (
    <fieldset disabled={disabled} className="lab-fields">
      <legend className="lab-section-title">Trip inputs</legend>
      <div className="lab-field-grid">
        {['start_id', 'destination_id'].map((key) => (
          <label key={key}>
            {key === 'start_id' ? 'Start' : 'Destination'}
            <select value={inputs[key]} onChange={(e) => set(key, e.target.value)}>
              {catalog.endpoints.map((endpoint) => (
                <option key={endpoint.id} value={endpoint.id}>
                  {endpoint.label}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label>
          Departure date
          <input
            type="date"
            required
            value={inputs.departure_date}
            onChange={(e) => set('departure_date', e.target.value)}
          />
        </label>
        <label>
          Departure time
          <input
            type="time"
            required
            value={inputs.departure_time}
            onChange={(e) => set('departure_time', e.target.value)}
          />
        </label>
        {numberField(
          'num_stops',
          'Maximum attractions',
          catalog.limits.min_stops,
          catalog.limits.max_stops
        )}
        {numberField('traveler_count', 'Travelers', 1)}
        {numberField('budget', 'Hotel target / room / night (USD)', 0)}
      </div>
      <p className="lab-note">
        Origin-local departure time.{' '}
        <HelpTip label="trip input validation">
          The server resolves these reviewed city choices and validates dates, occupancy and
          scheduling. Live departures must be upcoming.
        </HelpTip>
      </p>
      <details open>
        <summary>Trip interests</summary>
        <InterestsPie
          attributes={catalog.attributes}
          weights={inputs.persona_weights}
          onChange={(weights) => set('persona_weights', weights)}
          disabled={disabled}
        />
      </details>
      <details>
        <summary>Rooms and travelers</summary>
        <p className="lab-note">Room occupants must add up to the traveler count.</p>
        {inputs.hotel_rooms.map((room, index) => (
          <div className="lab-room" key={index}>
            <label>
              Room {index + 1} adults
              <input
                type="number"
                min="1"
                max={catalog.limits.max_guests_per_room}
                required
                value={room.adults}
                onChange={(e) =>
                  setRoom(index, {
                    ...room,
                    adults: e.target.value === '' ? '' : Number(e.target.value),
                  })
                }
              />
            </label>
            {room.child_ages.map((age, child) => (
              <div className="lab-inline" key={child}>
                <label>
                  Room {index + 1} child {child + 1} age
                  <input
                    type="number"
                    min="0"
                    max={catalog.limits.max_child_age}
                    required
                    value={age}
                    onChange={(e) =>
                      setRoom(index, {
                        ...room,
                        child_ages: room.child_ages.map((old, i) =>
                          i === child ? (e.target.value === '' ? '' : Number(e.target.value)) : old
                        ),
                      })
                    }
                  />
                </label>
                <button
                  type="button"
                  onClick={() =>
                    setRoom(index, {
                      ...room,
                      child_ages: room.child_ages.filter((_, i) => i !== child),
                    })
                  }
                >
                  Remove child {child + 1}
                </button>
              </div>
            ))}
            <div className="lab-inline">
              <button
                type="button"
                disabled={
                  room.adults + room.child_ages.length >= catalog.limits.max_guests_per_room
                }
                onClick={() => setRoom(index, { ...room, child_ages: [...room.child_ages, 5] })}
              >
                Add child to room {index + 1}
              </button>
              {inputs.hotel_rooms.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    set(
                      'hotel_rooms',
                      inputs.hotel_rooms.filter((_, i) => i !== index)
                    )
                  }
                >
                  Remove room {index + 1}
                </button>
              )}
            </div>
          </div>
        ))}
        <button
          type="button"
          disabled={inputs.hotel_rooms.length >= catalog.limits.max_rooms}
          onClick={() => set('hotel_rooms', [...inputs.hotel_rooms, { adults: 1, child_ages: [] }])}
        >
          Add room
        </button>
      </details>
      <details>
        <summary>Car and evening schedule</summary>
        <label>
          Car choice
          <select
            value={inputs.car_status}
            onChange={(e) =>
              onChange({
                ...inputs,
                car_status: e.target.value,
                car: e.target.value === 'skipped' ? null : { year: '', make: '', model: '' },
              })
            }
          >
            <option value="skipped">Skip car details</option>
            <option value="provided">Provide a car</option>
          </select>
        </label>
        {inputs.car_status === 'provided' && (
          <div className="lab-field-grid">
            {['year', 'make', 'model'].map((key) => (
              <label key={key}>
                Car {key}
                <input
                  required
                  type={key === 'year' ? 'number' : 'text'}
                  value={inputs.car?.[key] ?? ''}
                  onChange={(e) =>
                    set('car', {
                      ...inputs.car,
                      [key]:
                        key === 'year' && e.target.value ? Number(e.target.value) : e.target.value,
                    })
                  }
                />
              </label>
            ))}
          </div>
        )}
        <div className="lab-field-grid">
          {[
            'preferred_hotel_arrival',
            'latest_hotel_arrival',
            'latest_destination_arrival',
            'morning_restart',
            'late_cutoff',
          ].map((key) => (
            <label key={key}>
              {title(key)}
              <input
                type={key === 'late_cutoff' ? 'text' : 'time'}
                placeholder={key === 'late_cutoff' ? '24:00' : undefined}
                required={key !== 'latest_destination_arrival'}
                value={policy[key] ?? ''}
                onChange={(e) =>
                  set('scheduling_policy', { ...policy, [key]: e.target.value || null })
                }
              />
            </label>
          ))}
        </div>
        <label className="lab-checkbox">
          <input
            type="checkbox"
            checked={policy.late_driving}
            onChange={(e) =>
              set('scheduling_policy', { ...policy, late_driving: e.target.checked })
            }
          />
          Allow late driving
        </label>
        <p className="lab-note">
          A blank destination arrival uses the server default. Late cutoff accepts 24:00 for
          midnight.
        </p>
        <p>Optional evening suggestions</p>
        {['food', 'culture', 'nightlife'].map((interest) => (
          <label className="lab-checkbox" key={interest}>
            <input
              type="checkbox"
              checked={inputs.evening_interests.includes(interest)}
              onChange={(e) =>
                set(
                  'evening_interests',
                  e.target.checked
                    ? [...inputs.evening_interests, interest]
                    : inputs.evening_interests.filter((key) => key !== interest)
                )
              }
            />
            {interest}
          </label>
        ))}
      </details>
    </fieldset>
  );
}

TripInputs.propTypes = {
  inputs: PropTypes.object.isRequired,
  catalog: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool.isRequired,
};
