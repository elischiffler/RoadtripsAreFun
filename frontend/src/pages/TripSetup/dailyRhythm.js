export const DEFAULT_DAILY_RHYTHM = Object.freeze({
  driveStart: 9,
  driveEnd: 20,
  sleepStart: 22,
  sleepEnd: 7,
});

export const hourLabel = (hour) => `${String(hour).padStart(2, '0')}:00`;

function hoursBetween(start, end) {
  const hours = [];
  for (let hour = start; hour !== end; hour = (hour + 1) % 24) {
    hours.push(hour);
    if (hours.length === 24) break;
  }
  return hours;
}

export function dailyScheduleFromRhythm(rhythm) {
  const keys = Object.keys(DEFAULT_DAILY_RHYTHM);
  if (
    !rhythm ||
    keys.some((key) => !Number.isInteger(rhythm[key]) || rhythm[key] < 0 || rhythm[key] > 23)
  )
    throw new Error('Choose valid driving and sleep hours.');
  if (rhythm.driveStart === rhythm.driveEnd) throw new Error('Allow at least one driving hour.');
  if (rhythm.sleepStart === rhythm.sleepEnd) throw new Error('Choose a sleep window.');
  const driving = hoursBetween(rhythm.driveStart, rhythm.driveEnd);
  const sleeping = hoursBetween(rhythm.sleepStart, rhythm.sleepEnd);
  if (driving.some((hour) => sleeping.includes(hour)))
    throw new Error('Driving and sleep hours overlap.');
  const slots = Array(24).fill('rest');
  driving.forEach((hour) => (slots[hour] = 'drive'));
  sleeping.forEach((hour) => (slots[hour] = 'sleep'));
  return { slots, timezone: 'route_local' };
}

export function rhythmFromDailySchedule(schedule) {
  if (schedule === undefined || schedule === null) return null;
  if (
    schedule.timezone !== 'route_local' ||
    !Array.isArray(schedule.slots) ||
    schedule.slots.length !== 24 ||
    schedule.slots.some((slot) => !['drive', 'rest', 'sleep'].includes(slot))
  )
    throw new Error('This daily rhythm is unavailable.');
  const block = (label) => {
    const starts = schedule.slots
      .map((slot, hour) =>
        slot === label && schedule.slots[(hour + 23) % 24] !== label ? hour : -1
      )
      .filter((hour) => hour >= 0);
    if (starts.length !== 1) throw new Error('Use one driving window and one sleep window.');
    const start = starts[0];
    let end = (start + 1) % 24;
    while (schedule.slots[end] === label) end = (end + 1) % 24;
    return [start, end];
  };
  const [driveStart, driveEnd] = block('drive');
  const [sleepStart, sleepEnd] = block('sleep');
  const rhythm = { driveStart, driveEnd, sleepStart, sleepEnd };
  dailyScheduleFromRhythm(rhythm);
  return rhythm;
}

export function schedulingPolicyFromDraft(draft) {
  const rhythm = draft.dailyRhythm ?? rhythmFromDailySchedule(draft.schedule?.daily_schedule);
  return rhythm ? { daily_schedule: dailyScheduleFromRhythm(rhythm) } : { ...draft.schedule };
}

export function supportsOvernightRhythm(rhythm) {
  if (!rhythm) return true;
  try {
    const { slots } = dailyScheduleFromRhythm(rhythm);
    const end = rhythm.driveEnd === 0 ? 24 : rhythm.driveEnd;
    return end >= 18 && end > rhythm.driveStart && slots[0] === 'sleep';
  } catch {
    return false;
  }
}
