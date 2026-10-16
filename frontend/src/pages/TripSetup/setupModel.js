export const INTERESTS = {
  scenery: 'Scenic views',
  nature: 'Nature',
  hiking_outdoors: 'Walks and hikes',
  food: 'Food',
  history: 'History',
  culture_arts: 'Art and culture',
  nightlife: 'Nightlife',
  shopping: 'Shopping',
  beaches_water: 'Beaches and water',
  adventure: 'Adventure',
  relaxation: 'Relaxation',
  unique_local_experiences: 'Local discoveries',
  family_friendliness: 'Family activities',
  crowd_avoidance: 'Quieter places',
};

// Factual display subset of the existing reviewed CC0 Boulder catalog.
// No fixture ratings, opening status, coordinates or timing are copied.
export const PLACES = [
  {
    id: 'boulder:284',
    name: 'Halfway House',
    description: 'A Boulder trailhead on Flagstaff Road.',
    url: 'https://bouldercolorado.gov/trailhead/halfway-house',
  },
  {
    id: 'boulder:272',
    name: 'Realization Point',
    description: 'A Boulder trailhead on Flagstaff Road.',
    url: 'https://bouldercolorado.gov/trailhead/realization-point',
  },
];
// Mirrors backend/app/routing/occupancy.py; server validation remains authoritative.
export const MAX_SETUP_ROOMS = 4;
export const PLACE_REASONS = ['nature', 'hiking_outdoors', 'scenery'];
export const STEPS = [
  'Where and when',
  'People and rooms',
  'What you enjoy',
  'Car and timing',
  'Review',
];

export function newSetupDraft() {
  return {
    start: '',
    destination: '',
    date: '',
    time: '09:00',
    stops: '3',
    travelers: '1',
    rooms: [{ adults: '1', children: '' }],
    budget: '150',
    interests: [],
    ratings: {},
    customWeights: null,
    carStatus: 'unanswered',
    year: '',
    make: '',
    model: '',
    schedule: {
      preferred_hotel_arrival: '18:00',
      latest_hotel_arrival: '20:00',
      latest_destination_arrival: '21:00',
      morning_restart: '09:00',
      late_driving: false,
      late_cutoff: '24:00',
    },
  };
}

export function normalizeWeights(values) {
  const keys = Object.keys(INTERESTS);
  if (
    !values ||
    Object.keys(values).length !== keys.length ||
    keys.some(
      (key) => typeof values[key] !== 'number' || !Number.isFinite(values[key]) || values[key] < 0
    )
  )
    throw new Error('Choose valid, non-negative interest amounts.');
  const total = Object.values(values).reduce((sum, value) => sum + value, 0);
  if (!Number.isFinite(total) || total <= 0)
    throw new Error('Give at least one interest a value above zero.');
  return Object.fromEntries(keys.map((key) => [key, values[key] / total]));
}

export function preferenceWeights(draft) {
  if (draft.customWeights) return normalizeWeights(draft.customWeights);
  const raw = Object.fromEntries(
    Object.keys(INTERESTS).map((key) => [key, draft.interests.includes(key) ? 4 : 1])
  );
  for (const place of PLACES) {
    const answer = draft.ratings[place.id];
    if (![1, 3, 5].includes(answer?.rating)) continue;
    for (const key of answer.reasons ?? []) {
      if (PLACE_REASONS.includes(key))
        raw[key] = Math.max(0.25, raw[key] + (answer.rating - 3) / 4);
    }
  }
  return normalizeWeights(raw);
}

export function roomInputs(draft) {
  return draft.rooms.map((room) => ({
    adults: Number(room.adults),
    child_ages: room.children.trim()
      ? room.children.split(',').map((age) => Number(age.trim()))
      : [],
  }));
}

export function setupErrors(draft, step) {
  const errors = {};
  const needed = (key, label) => {
    if (!draft[key].trim()) errors[key] = label;
  };
  if (step === 0) {
    needed('start', 'Enter your starting city or address.');
    needed('destination', 'Enter your destination.');
    if (
      draft.start.trim() &&
      draft.start.trim().toLowerCase() === draft.destination.trim().toLowerCase()
    )
      errors.destination = 'Choose a different destination.';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date)) errors.date = 'Choose a departure date.';
    if (!/^\d{2}:\d{2}$/.test(draft.time)) errors.time = 'Choose a departure time.';
    if (!draft.stops || !Number.isInteger(Number(draft.stops)) || Number(draft.stops) < 1)
      errors.stops = 'Choose at least one attraction.';
  }
  if (step === 1) {
    const rooms = roomInputs(draft);
    if (
      !draft.travelers ||
      !Number.isInteger(Number(draft.travelers)) ||
      Number(draft.travelers) < 1 ||
      Number(draft.travelers) > 24
    )
      errors.travelers = 'Enter 1 to 24 people, including you.';
    if (!draft.budget || !Number.isFinite(Number(draft.budget)) || Number(draft.budget) < 0)
      errors.budget = 'Enter a hotel target of zero or more.';
    if (
      rooms.some(
        (r, i) =>
          !draft.rooms[i].adults ||
          !Number.isInteger(r.adults) ||
          r.adults < 1 ||
          r.adults + r.child_ages.length > 6 ||
          (draft.rooms[i].children.trim() &&
            !/^\s*\d{1,2}\s*(,\s*\d{1,2}\s*)*$/.test(draft.rooms[i].children)) ||
          r.child_ages.some((age) => !Number.isInteger(age) || age < 0 || age > 17)
      )
    )
      errors.rooms =
        'Each room needs an adult and at most 6 people. Use child ages from 0 to 17, separated by commas.';
    else if (
      rooms.reduce((sum, r) => sum + r.adults + r.child_ages.length, 0) !== Number(draft.travelers)
    )
      errors.rooms = 'Room occupants must add up to the total people.';
  }
  if (step === 2) {
    try {
      preferenceWeights(draft);
    } catch (error) {
      errors.interests = error.message;
    }
  }
  if (step === 3) {
    if (!['skipped', 'provided'].includes(draft.carStatus))
      errors.carStatus = 'Choose whether to add your car.';
    if (draft.carStatus === 'provided') {
      needed('make', 'Enter the car make.');
      needed('model', 'Enter the car model.');
      if (!/^\d{4}$/.test(draft.year)) errors.year = 'Enter the four-digit car year.';
    }
    if (draft.schedule.preferred_hotel_arrival > draft.schedule.latest_hotel_arrival)
      errors.schedule = 'Your preferred hotel arrival must be before the latest hotel arrival.';
    const clocks = Object.entries(draft.schedule).filter(
      ([key]) => !['late_driving', 'late_cutoff'].includes(key)
    );
    if (
      clocks.some(([, v]) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) ||
      !/^(([01]\d|2[0-3]):[0-5]\d|24:00)$/.test(draft.schedule.late_cutoff)
    )
      errors.schedule = 'Choose valid daily times.';
  }
  return errors;
}

export function restoreDraft(value) {
  try {
    const { version, draft, step } = JSON.parse(value);
    const initial = newSetupDraft();
    if (version !== 1 || !draft || Object.keys(initial).some((key) => !(key in draft))) return null;
    for (const [key, baseline] of Object.entries(initial)) {
      if (
        typeof baseline === 'string' &&
        (typeof draft[key] !== 'string' || draft[key].length > 500)
      )
        return null;
    }
    if (
      !Array.isArray(draft.rooms) ||
      !draft.rooms.length ||
      draft.rooms.length > MAX_SETUP_ROOMS ||
      draft.rooms.some((r) => typeof r.adults !== 'string' || typeof r.children !== 'string') ||
      !Array.isArray(draft.interests) ||
      draft.interests.some((k) => !(k in INTERESTS)) ||
      !draft.ratings ||
      typeof draft.ratings !== 'object' ||
      !draft.schedule ||
      Object.keys(initial.schedule).some(
        (key) => typeof draft.schedule[key] !== typeof initial.schedule[key]
      )
    )
      return null;
    for (const answer of Object.values(draft.ratings)) {
      if (
        !answer ||
        ![null, 1, 3, 5].includes(answer.rating) ||
        !Array.isArray(answer.reasons) ||
        answer.reasons.some((k) => !PLACE_REASONS.includes(k))
      )
        return null;
    }
    if (
      draft.customWeights &&
      (Object.keys(draft.customWeights).length !== Object.keys(INTERESTS).length ||
        Object.keys(INTERESTS).some(
          (key) =>
            typeof draft.customWeights[key] !== 'number' ||
            !Number.isFinite(draft.customWeights[key]) ||
            draft.customWeights[key] < 0
        ))
    )
      return null;
    return { draft, step: Number.isInteger(step) && step >= 0 && step < STEPS.length ? step : 0 };
  } catch {
    return null;
  }
}
