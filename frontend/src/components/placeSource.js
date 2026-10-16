// Keep source facts distinct from live availability and subjective ratings.
export function placeSourceLines(place) {
  if (!place?.source_release && !place?.source_attribution && !place?.source_updated_at) return [];
  const updated = place.source_updated_at;
  const timestamp = updated ? new Date(updated) : null;
  return [
    place.source_attribution ? `Source: ${place.source_attribution}` : 'Catalog source',
    place.source_release ? `Source release: ${place.source_release}` : null,
    timestamp && !Number.isNaN(timestamp.getTime())
      ? `Source evidence updated: ${timestamp.toISOString().slice(0, 10)} (UTC)`
      : 'Source evidence date unknown',
    'Catalog identity; opening hours and current availability are unverified.',
  ].filter(Boolean);
}
