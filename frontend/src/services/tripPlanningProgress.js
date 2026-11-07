// These are explicit planning milestones, not an estimate of elapsed or remaining time.
const MILESTONES = {
  'details.confirmed': [40, 'Your trip details are ready'],
  'route.initial': [70, 'Your starting route is ready'],
  'route.gathering': [74, 'Places along the route have been gathered'],
  'route.detours': [78, 'Driving detours have been checked'],
  'route.solver': [82, 'A set of stops has been compared'],
  'route.schedule': [86, 'A daily schedule has been checked'],
  'route.final_reroute': [88, 'Driving between the stops has been checked'],
  'route.validation': [90, 'Final route timing has been checked'],
  'candidate.checked': [91, 'Your trip options are checked'],
  'route.ready': [92, 'Your route is ready'],
  'itinerary.ready': [96, 'Your day-by-day itinerary is ready'],
};
const ACTIVE = {
  'route.gathering': 'Finding places that fit your trip',
  'route.detours': 'Checking driving detours',
  'route.solver': 'Comparing possible stops',
  'route.schedule': 'Checking daily timing and overnight stays',
  'route.final_reroute': 'Checking the roads between stops',
  'route.validation': 'Checking the final route timing',
};

export const newPlanningProgress = () => ({
  percent: 0,
  label: 'Ready to plan',
  routeReady: false,
  itineraryReady: false,
  saved: false,
  failed: false,
});

export function advancePlanningProgress(previous, event) {
  if (event.type === 'failed')
    return { ...previous, failed: true, label: 'Your trip needs attention' };
  if (event.type === 'resume') return { ...previous, failed: false, label: 'Finishing your trip' };
  if (event.type !== 'progress') return previous;
  const completed = event.state === 'completed';
  const next = { ...previous };
  if (completed && event.stage === 'route.ready') next.routeReady = true;
  if (completed && event.stage === 'itinerary.ready') {
    next.itineraryReady = true;
    // A previously saved partial route does not mean the new itinerary is saved.
    next.saved = false;
  }
  if (completed && event.stage === 'trip.saved') next.saved = true;
  const milestone = completed ? MILESTONES[event.stage] : undefined;
  if (milestone) {
    next.percent = Math.max(previous.percent, milestone[0]);
    next.label = milestone[1];
  } else if (event.state === 'started' && ACTIVE[event.stage]) next.label = ACTIVE[event.stage];
  if (next.routeReady && next.itineraryReady && next.saved) {
    next.percent = 100;
    next.label = 'Your route and itinerary are saved';
    next.failed = false;
  } else if (completed && event.stage === 'trip.saved') {
    next.label = 'Your route is saved; the itinerary still needs attention';
  }
  return next;
}
