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

export function visitEstimateLabel(duration) {
  if (duration?.source === 'ai_estimate') return 'AI-estimated visit';
  if (duration?.source === 'conservative_fallback') return 'Estimated visit (fallback)';
  return null;
}
