import PropTypes from 'prop-types';
import { compactTimestamp } from './placeTiming';

function scheduledMinutes(meal) {
  if (meal.status !== 'reserved') return null;
  if (
    !compactTimestamp(meal.arrival_time, meal.timezone) ||
    !compactTimestamp(meal.departure_time, meal.timezone)
  )
    return null;
  const start = Date.parse(meal.arrival_time);
  const end = Date.parse(meal.departure_time);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  return Math.round((end - start) / 60000);
}

function MealClock({ value, timezone }) {
  return (
    <time dateTime={value}>
      {compactTimestamp(value, timezone)?.time || value?.slice(11, 16) || 'Time to choose'}
    </time>
  );
}

MealClock.propTypes = { value: PropTypes.string, timezone: PropTypes.string };

export default function MealBreaks({ meals }) {
  const scheduled = meals.filter((meal) => scheduledMinutes(meal) !== null);
  const open = meals.filter((meal) => scheduledMinutes(meal) === null);
  return [
    { title: 'Meal breaks', rows: scheduled, reserved: true },
    { title: 'Open meal windows', rows: open, reserved: false },
  ].map(({ title, rows, reserved }) =>
    rows.length ? (
      <section key={title} className="trip-meal-windows" aria-label={title}>
        <h3 className="rt-title">{title}</h3>
        <ul>
          {rows.map((meal, index) => (
            <li key={meal.id || index}>
              <h4 className="rt-copy">{meal.name}</h4>
              <p className="rt-caption">
                <MealClock
                  value={reserved ? meal.arrival_time : meal.window_start}
                  timezone={meal.timezone}
                />
                {' – '}
                <MealClock
                  value={reserved ? meal.departure_time : meal.window_end}
                  timezone={meal.timezone}
                />
                {meal.timezone ? ` (${meal.timezone})` : ''}
              </p>
              {reserved && meal.notice && <p className="rt-caption">{meal.notice}</p>}
              {reserved && <p className="rt-caption">{scheduledMinutes(meal)} minutes set aside</p>}
              <p className="rt-caption">
                {reserved
                  ? 'Time set aside in your schedule. No dining place is selected or booked.'
                  : meal.status === 'reserved'
                    ? 'This saved meal has no usable scheduled interval. Regenerate the trip to reserve time.'
                    : meal.notice ||
                      'Open planning window; no time or place is reserved. May overlap driving or visits; adjust the time.'}
              </p>
            </li>
          ))}
        </ul>
      </section>
    ) : null
  );
}

MealBreaks.propTypes = { meals: PropTypes.array.isRequired };
