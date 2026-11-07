import PropTypes from 'prop-types';
import './LodgingDetails.css';

function calendarDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return null;
  return {
    date,
    label: new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(date),
  };
}

/** Quote calendar dates are supplied by the server, never inferred from travel clocks. */
export default function LodgingDetails({ lodging }) {
  if (!lodging) return null;
  const checkIn = calendarDate(lodging.check_in_date),
    checkOut = calendarDate(lodging.check_out_date);
  const valid =
    checkIn &&
    checkOut &&
    Number.isInteger(lodging.nights) &&
    lodging.nights > 0 &&
    (checkOut.date - checkIn.date) / 86400000 === lodging.nights &&
    lodging.access_status === 'confirmation_required';
  return (
    <section className="lodging-details rt-caption" aria-label="Hotel quote dates">
      {valid ? (
        <>
          <p>
            Quote dates · {lodging.nights} {lodging.nights === 1 ? 'night' : 'nights'}
          </p>
          <p>
            <time dateTime={lodging.check_in_date} aria-label={`Quoted check-in: ${checkIn.label}`}>
              {checkIn.label}
            </time>
            {' – '}
            <time
              dateTime={lodging.check_out_date}
              aria-label={`Quoted check-out: ${checkOut.label}`}
            >
              {checkOut.label}
            </time>
          </p>
          <p>
            {typeof lodging.notice === 'string' && lodging.notice.trim()
              ? lodging.notice
              : 'Confirm arrival and departure access with the property before booking. No room is booked.'}
          </p>
        </>
      ) : (
        <p>
          Quote dates are unavailable. Confirm dates and access with the property before booking.
        </p>
      )}
    </section>
  );
}
LodgingDetails.propTypes = { lodging: PropTypes.object };
