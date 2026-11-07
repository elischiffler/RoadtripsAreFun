import axios from './protectedRequest';
import { backendAuthConfig } from './backendAuth';
import { getSession, isCurrentSession, SessionError } from './session';
import {
  INTERESTS,
  newSetupDraft,
  normalizeWeights,
  preferenceProfiles,
} from '../pages/TripSetup/setupModel';
import { rhythmFromDailySchedule, schedulingPolicyFromDraft } from '../pages/TripSetup/dailyRhythm';

const endpoint = () => import.meta.env.VITE_BACKEND_SERVER + 'preference-profiles';
export async function loadPreferenceProfiles() {
  const { data } = await axios.get(endpoint(), { ...backendAuthConfig(), timeout: 15000 });
  if (!Array.isArray(data)) throw new Error('Preference profiles could not be loaded.');
  return data;
}
export async function savePreferenceProfile(profile) {
  const { id, name, choices } = profile;
  const { data } = await axios.put(
    endpoint() + '/' + encodeURIComponent(id),
    { name, choices },
    { ...backendAuthConfig(), timeout: 15000 }
  );
  return data;
}
export async function deletePreferenceProfile(id) {
  await axios.delete(endpoint() + '/' + encodeURIComponent(id), {
    ...backendAuthConfig(),
    timeout: 15000,
  });
}

// Deliberate allowlist: route, date, stops, budget, rooms and account memory
// cannot leak into a reusable set. Only stated/manual interests are reusable;
// the comparison-derived profile and its trip-only blend remain private.
export function choicesFromDraft(draft) {
  if (!['skipped', 'provided'].includes(draft.carStatus))
    throw new Error('Choose whether to include a car.');
  return {
    car_status: draft.carStatus,
    car:
      draft.carStatus === 'provided'
        ? { year: Number(draft.year), make: draft.make.trim(), model: draft.model.trim() }
        : null,
    scheduling_policy: schedulingPolicyFromDraft(draft),
    persona_weights: preferenceProfiles(draft).stated,
  };
}

export function applyPreferenceChoices(draft, choices) {
  const weights = normalizeWeights(choices.persona_weights);
  const initial = newSetupDraft();
  if (!['skipped', 'provided'].includes(choices.car_status)) throw new Error('Invalid saved car.');
  if (choices.car_status === 'provided' && !choices.car) throw new Error('Missing saved car.');
  // Explicit reuse replaces only these choices; never reset existing trip input.
  return {
    ...draft,
    carStatus: choices.car_status,
    year: choices.car ? String(choices.car.year) : '',
    make: choices.car?.make ?? '',
    model: choices.car?.model ?? '',
    schedule: { ...initial.schedule, ...choices.scheduling_policy },
    dailyRhythm: rhythmFromDailySchedule(choices.scheduling_policy.daily_schedule),
    interests: [],
    ratings: {},
    comparisonAnswers: {},
    customWeights: weights,
  };
}

export function samePreferenceChoices(a, b) {
  const canonical = (value) => {
    if (value && typeof value === 'object' && !Array.isArray(value))
      return Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, canonical(value[key])])
      );
    // Normalization can change the least significant floating-point digit.
    return typeof value === 'number' ? Number(value.toFixed(10)) : value;
  };
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

export async function saveNewTripPreferences(draft, id) {
  const session = getSession();
  const choices = choicesFromDraft(draft);
  const profiles = await loadPreferenceProfiles();
  if (!isCurrentSession(session)) throw new SessionError('session-changed');
  if (profiles.some((profile) => samePreferenceChoices(profile.choices, choices))) return;
  const car = choices.car;
  const ranked = Object.entries(choices.persona_weights).sort((a, b) => b[1] - a[1]);
  const interests =
    ranked[0][1] - ranked.at(-1)[1] < 1e-10
      ? 'All interests'
      : ranked
          .slice(0, 2)
          .map(([key]) => INTERESTS[key])
          .join(' + ');
  const name = [car ? `${car.year} ${car.make} ${car.model}` : null, interests]
    .filter(Boolean)
    .join(' · ')
    .slice(0, 80);
  await savePreferenceProfile({ id, name, choices });
}
