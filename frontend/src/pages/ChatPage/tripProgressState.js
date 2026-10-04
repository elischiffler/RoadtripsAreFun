const labels = {
  'agent.extract_details': 'Checking your trip details',
  'agent.model': 'Preparing your reply',
  'attractions.query': 'Finding places to stop',
  'route.solver': 'Choosing stops for your route',
  'route.schedule': 'Planning your driving days',
  'route.overnight': 'Finding an overnight stay',
  'hotels.lookup': 'Finding hotels near your route',
  'hotels.google_search': 'Searching hotel options',
  'hotels.verify_listing': 'Checking hotel prices and locations',
  'hotels.ratings': 'Comparing hotel options',
  'mapbox.request': 'Checking driving directions',
  'route.final_reroute': 'Finalizing your route',
  'itinerary.build': 'Building your itinerary',
  'agent.persist_memory': 'Saving your trip details',
};

export function updateTripProgress(previous, event) {
  if (event.type !== 'progress' || !labels[event.stage]) return previous;
  const key = [event.stage, event.query, event.day, event.attempt, event.iteration].join(':');
  const entries = [...(previous?.entries ?? [])];
  const index = entries.findLastIndex((entry) => entry.key === key && entry.state === 'started');
  const entry = {
    key,
    label: labels[event.stage],
    state: event.state,
    durationMs: event.durationMs,
  };
  if (index >= 0 && event.state !== 'started') entries[index] = entry;
  else entries.push(entry);
  return { ...previous, entries: entries.slice(-12) };
}
