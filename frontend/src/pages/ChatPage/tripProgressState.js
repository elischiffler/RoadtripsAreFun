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
  'evening.discovery': 'Checking optional places near your hotel',
  'itinerary.build': 'Building your itinerary',
  'agent.persist_memory': 'Saving your trip details',
};

const number = (value) => (Number.isInteger(value) && value >= 0 && value <= 10000 ? value : null);
const name = (value) =>
  typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, 48) : '';

function liveLabel(event) {
  const count = number(event.collected);
  const hotels = number(event.hotels);
  const query = number(event.query);
  const queries = number(event.queries);
  const area = query && queries ? `area ${query} of ${queries}` : 'your route';
  switch (event.stage) {
    case 'attractions.query':
      return event.state === 'started'
        ? `${count ? `${count} ${count === 1 ? 'place' : 'places'} collected · ` : ''}Searching ${area}`
        : `${count ?? 0} ${count === 1 ? 'place' : 'places'} collected · checked ${area}`;
    case 'attractions.collected':
      return count !== null ? `Found ${name(event.name) || 'a place'} · ${count} collected` : null;
    case 'hotels.search_area':
      return name(event.city) ? `Searching hotels in ${name(event.city)}` : null;
    case 'hotels.verify_listing':
      return event.state === 'started' && number(event.attempt)
        ? `Checking hotel ${event.attempt} · price and location`
        : null;
    case 'hotels.collected':
      return hotels !== null ? `Verified ${name(event.name) || 'a hotel'} · ${hotels} found` : null;
    case 'hotels.verified':
      return hotels !== null ? `${hotels} verified hotel options found` : null;
    case 'hotels.no_nearby':
      return 'No nearby hotels · checking an earlier stop';
    case 'route.solver':
      return event.state === 'started' && number(event.candidates) !== null
        ? `Choosing stops from ${event.candidates} collected places`
        : null;
    case 'route.selected':
      return number(event.selected) !== null
        ? `${event.selected} stops selected · planning driving days`
        : null;
    case 'route.overnight':
      return event.state === 'started' && number(event.day)
        ? `Finding a stay for night ${event.day}${event.attempt > 1 ? ` · checking location ${event.attempt}` : ''}`
        : null;
    default:
      return null;
  }
}

export function updateTripProgress(previous, event) {
  if (event.type !== 'progress') return previous;
  const detail = event.state === 'failed' ? null : liveLabel(event);
  if (!labels[event.stage] && !detail) return previous;
  const key = [event.stage, event.query, event.day, event.attempt, event.iteration].join(':');
  const entries = [...(previous?.entries ?? [])];
  const index = entries.findLastIndex((entry) => entry.key === key && entry.state === 'started');
  const entry = {
    key,
    label: detail ?? labels[event.stage],
    state: event.state,
    durationMs: event.durationMs,
  };
  if (index >= 0 && event.state !== 'started') entries[index] = entry;
  else entries.push(entry);
  const current = entries.findLast((entry) => entry.state === 'started');
  const message =
    detail ?? (event.state === 'started' ? entry.label : (current?.label ?? 'Thinking'));
  return { ...previous, message, entries: entries.slice(-12) };
}
