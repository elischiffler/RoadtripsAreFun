import PropTypes from 'prop-types';
import { compactTimestamp } from './placeTiming';
import './PlaceTiming.css';

export default function PlaceTiming({ place }) {
  const arrival = compactTimestamp(place.arrival_time, place.timezone);
  const leaving =
    place.type === 'end' ? null : compactTimestamp(place.departure_time, place.timezone);
  if (!arrival && !leaving) return null;
  const shared =
    !arrival || !leaving || (arrival.day === leaving.day && arrival.offset === leaving.offset);
  const context = arrival ?? leaving;
  const clocks = [
    ['Arrival', arrival, place.arrival_time],
    ...(place.type === 'end' ? [] : [['Leaving', leaving, place.departure_time]]),
  ];
  return (
    <div className="place-timing" aria-label="Place timing">
      {shared && (
        <p className="place-timing-context">
          {context.date} · {context.zone}
        </p>
      )}
      <dl className="place-timing-clocks">
        {clocks.map(([label, clock, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>
              {clock ? (
                <>
                  <time dateTime={value} title={clock.label} aria-label={clock.label}>
                    {clock.time}
                  </time>
                  {!shared && (
                    <span className="place-timing-context">
                      {clock.date} · {clock.zone}
                    </span>
                  )}
                </>
              ) : (
                <span aria-label="Unavailable">—</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
PlaceTiming.propTypes = { place: PropTypes.object.isRequired };
