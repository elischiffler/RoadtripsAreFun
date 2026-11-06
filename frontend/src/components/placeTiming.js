export function localTimestamp(value, timezone) {
  if (typeof value !== 'string') return null;
  const match = value.match(
    /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/
  );
  if (!match || !Number.isFinite(new Date(value).getTime())) return null;
  if (timezone) {
    try {
      const label = new Intl.DateTimeFormat('en-US', {
        timeZone: timezone,
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZoneName: 'shortOffset',
      }).format(new Date(value));
      return `${label} (${timezone})`;
    } catch {
      // Old saved records may lack a valid IANA zone. Keep their explicit offset.
    }
  }
  return `${match[1]} ${match[2]} (UTC${match[3] === 'Z' ? '+00:00' : match[3]})`;
}

export function compactTimestamp(value, timezone) {
  const label = localTimestamp(value, timezone);
  if (!label) return null;
  let date = new Date(value);
  let zone = timezone;
  let zoneLabel;
  try {
    if (!zone) throw new RangeError('Missing time zone');
    new Intl.DateTimeFormat('en-US', { timeZone: zone }).format(date);
  } catch {
    // Preserve the saved wall clock and offset instead of using the browser zone.
    date = new Date(`${value.slice(0, 16)}:00Z`);
    zone = 'UTC';
    const offset = value.match(/(Z|[+-]\d{2}:\d{2})$/)[1];
    zoneLabel = offset === 'Z' ? 'UTC' : `UTC${offset}`;
  }
  const format = (options) =>
    new Intl.DateTimeFormat('en-US', { timeZone: zone, ...options }).format(date);
  const zoneName = (style) =>
    new Intl.DateTimeFormat('en-US', { timeZone: zone, timeZoneName: style })
      .formatToParts(date)
      .find((part) => part.type === 'timeZoneName').value;
  return {
    date: format({ month: 'short', day: 'numeric' }),
    day: format({ year: 'numeric', month: 'numeric', day: 'numeric' }),
    time: format({ hour: 'numeric', minute: '2-digit' }),
    zone: zoneLabel ?? zoneName('short'),
    offset: zoneLabel ?? zoneName('shortOffset'),
    label,
  };
}
