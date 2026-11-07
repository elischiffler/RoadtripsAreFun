import { expect, it } from 'vitest';
import {
  DEFAULT_DAILY_RHYTHM,
  dailyScheduleFromRhythm,
  rhythmFromDailySchedule,
  schedulingPolicyFromDraft,
  supportsOvernightRhythm,
} from '../pages/TripSetup/dailyRhythm';
import {
  hotelSetupErrors,
  newSetupDraft,
  restoreDraft,
  setupErrors,
} from '../pages/TripSetup/setupModel';
import { approximateRestRegions } from '../pages/TripSetup/tripPreparation';

it('keeps all24 meaningful slots and omits conflicting legacy clocks on opt-in', () => {
  const draft = newSetupDraft();
  const policy = schedulingPolicyFromDraft(draft);
  expect(Object.keys(policy)).toEqual(['daily_schedule']);
  expect(policy.daily_schedule.slots).toHaveLength(24);
  expect(policy.daily_schedule.slots[9]).toBe('drive');
  expect(policy.daily_schedule.slots[20]).toBe('rest');
  expect(policy.daily_schedule.slots[22]).toBe('sleep');
  expect(rhythmFromDailySchedule(policy.daily_schedule)).toEqual(DEFAULT_DAILY_RHYTHM);
  expect(() => dailyScheduleFromRhythm({ ...DEFAULT_DAILY_RHYTHM, driveEnd: 23 })).toThrow(
    /overlap/
  );
  expect(() => dailyScheduleFromRhythm({ ...DEFAULT_DAILY_RHYTHM, driveEnd: 9 })).toThrow(
    /driving hour/
  );
});
it('supports midnight-wrapping one-day availability while declaring unsupported hotel rhythms', () => {
  const night = { driveStart: 20, driveEnd: 6, sleepStart: 8, sleepEnd: 16 };
  expect(rhythmFromDailySchedule(dailyScheduleFromRhythm(night))).toEqual(night);
  expect(supportsOvernightRhythm(night)).toBe(false);
  expect(supportsOvernightRhythm({ driveStart: 9, driveEnd: 0, sleepStart: 0, sleepEnd: 7 })).toBe(
    true
  );
  expect(supportsOvernightRhythm(DEFAULT_DAILY_RHYTHM)).toBe(true);
  const split = dailyScheduleFromRhythm(DEFAULT_DAILY_RHYTHM);
  split.slots[12] = 'rest';
  expect(() => rhythmFromDailySchedule(split)).toThrow(/one driving/);
});
it('preserves legacy drafts/timing until an explicit conversion and defers lodging validation', () => {
  const legacy = newSetupDraft();
  delete legacy.dailyRhythm;
  delete legacy.tripMode;
  const restored = restoreDraft(JSON.stringify({ version: 1, draft: legacy, step: 3 }));
  expect(restored.draft.dailyRhythm).toBeNull();
  expect(schedulingPolicyFromDraft(restored.draft)).toEqual(legacy.schedule);
  const draft = { ...newSetupDraft(), travelers: '3', budget: '-1' };
  expect(setupErrors(draft, 1)).toEqual({});
  expect(hotelSetupErrors(draft)).toHaveProperty('rooms');
  expect(hotelSetupErrors(draft)).toHaveProperty('budget');
  expect(setupErrors({ ...draft, date: '2027-06-01', time: '08:00' }, 3).schedule).toMatch(
    /Departure/
  );
});
it('projects only approximate rest regions along supplied road geometry without hotel claims', () => {
  const draft = { ...newSetupDraft(), time: '09:00' };
  const route = {
    duration: 20 * 3600,
    geometry: {
      coordinates: [
        [179, 40],
        [-179, 40],
      ],
    },
  };
  const areas = approximateRestRegions(route, draft);
  expect(areas).toHaveLength(1);
  expect(areas[0]).toMatchObject({ approximate: true, label: 'Possible rest region' });
  expect(Math.abs(areas[0].coordinates[1])).toBeGreaterThan(179);
  expect(approximateRestRegions({ ...route, duration: 3600 }, draft)).toEqual([]);
  expect(approximateRestRegions({ duration: 999999 }, draft)).toEqual([]);
});
