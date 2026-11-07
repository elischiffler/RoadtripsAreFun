const ERRORS = {
  rhythm_clock_conflict: [
    422,
    'A driving or sleep boundary falls in an ambiguous or missing local hour. Choose a different hour for this date.',
  ],
  rhythm_availability_conflict: [
    422,
    'A road leg falls outside driving availability in its next stop’s local time. Choose a later departure or edit the daily rhythm.',
  ],
  departure_not_upcoming: [422, 'Choose a departure date and time in the future.'],
  one_day_ineligible: [
    422,
    'This complete candidate cannot be confirmed as a trip of less than 12 hours without a hotel. Revise the trip or choose overnight planning.',
  ],
  candidate_expired: [
    410,
    'These trip options expired or are unavailable. Check trip options again explicitly.',
  ],
  candidate_cancelled: [
    410,
    'This trip option check was cancelled. Start a new check explicitly when ready.',
  ],
  candidate_inputs_changed: [409, 'Trip inputs changed. Check trip options again explicitly.'],
  candidate_busy: [
    409,
    'This trip option is already being confirmed. Keep waiting for that request.',
  ],
  candidate_already_confirmed: [
    409,
    'A different trip option was already confirmed. Check trip options again explicitly.',
  ],
  candidate_unavailable: [
    503,
    'Trip options could not be verified. Your draft is kept. Check again explicitly when ready.',
  ],
  candidate_cannot_fit: [
    422,
    'The candidate cannot fit the validated visit, meal and driving constraints. Revise the trip options.',
  ],
  unsupported_overnight_rhythm: [
    422,
    'This rhythm needs hotel arrival or sleep timing the nightly hotel source cannot validate. Choose evening arrival with overnight sleep, or an eligible one-day trip.',
  ],
  departure_outside_rhythm: [
    422,
    'Departure is outside your driving availability. Choose an available hour or edit your daily rhythm.',
  ],
};

export function candidateErrorMessage(status, code) {
  return Object.hasOwn(ERRORS, code) && ERRORS[code][0] === status ? ERRORS[code][1] : undefined;
}

export function safeCandidateError(error) {
  const status = error.response?.status;
  const code = error.response?.data?.code;
  const detail = candidateErrorMessage(status, code);
  return Object.assign(
    new Error(detail || 'Trip options could not be checked. Your draft is kept.'),
    {
      code: detail ? code : undefined,
      response: { status, data: detail ? { code, detail } : undefined },
    }
  );
}
