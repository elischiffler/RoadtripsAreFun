/** Stable identities survive reload and reordering; occurrence distinguishes identical visits. */
export function itineraryEntries(itinerary = []) {
  const occurrences = new Map();
  return (Array.isArray(itinerary) ? itinerary : []).map((day) => ({
    day,
    meals: (Array.isArray(day.stops) ? day.stops : []).filter((stop) => stop?.kind === 'meal'),
    stops: (Array.isArray(day.stops) ? day.stops : [])
      .filter((stop) => stop && !stop.paired_departure && stop.kind !== 'meal')
      .map((stop) => {
        const identity = JSON.stringify([
          stop.provider_id || stop.id || stop.name || '',
          stop.address || '',
          stop.coordinates || null,
          day.date || '',
          stop.arrival_time || stop.time || '',
          stop.kind || stop.type || '',
          Boolean(stop.optional),
        ]);
        const occurrence = occurrences.get(identity) || 0;
        occurrences.set(identity, occurrence + 1);
        return { stop, id: `visit:${encodeURIComponent(identity)}:${occurrence}` };
      }),
  }));
}

export function visitedStopIds(presentation) {
  return new Set(
    Array.isArray(presentation?.visitedStopIds)
      ? presentation.visitedStopIds.filter((id) => typeof id === 'string')
      : []
  );
}

export function toggleVisited(presentation, id) {
  const visited = visitedStopIds(presentation);
  if (visited.has(id)) visited.delete(id);
  else visited.add(id);
  return { ...presentation, visitedStopIds: [...visited] };
}

export const validStopCoordinates = (point) =>
  Array.isArray(point) &&
  point.length === 2 &&
  point.every((value) => typeof value === 'number' && Number.isFinite(value)) &&
  Math.abs(point[0]) <= 90 &&
  Math.abs(point[1]) <= 180;
