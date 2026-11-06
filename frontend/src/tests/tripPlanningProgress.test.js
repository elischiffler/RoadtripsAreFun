import { describe, expect, it } from 'vitest';
import { advancePlanningProgress, newPlanningProgress } from '../services/tripPlanningProgress';
const done = (stage) => ({ type: 'progress', stage, state: 'completed' });

describe('honest trip planning milestones', () => {
  it('moves promptly to70 only after the initial driving route exists and then follows real stages', () => {
    let value = advancePlanningProgress(newPlanningProgress(), done('details.confirmed'));
    expect(value.percent).toBe(40);
    value = advancePlanningProgress(value, done('route.initial'));
    expect(value.percent).toBe(70);
    expect(advancePlanningProgress(value, { type: 'heartbeat' })).toBe(value);
    expect(
      advancePlanningProgress(value, {
        type: 'progress',
        stage: 'route.gathering',
        state: 'started',
      }).percent
    ).toBe(70);
    value = advancePlanningProgress(value, done('route.detours'));
    expect(value.percent).toBe(78);
    expect(advancePlanningProgress(value, done('route.gathering')).percent).toBe(78);
  });
  it('never reaches100 for a saved partial route or unsaved itinerary and clears a stale save on retry', () => {
    let value = advancePlanningProgress(newPlanningProgress(), done('route.ready'));
    value = advancePlanningProgress(value, done('trip.saved'));
    expect(value.percent).toBe(92);
    value = advancePlanningProgress(value, done('itinerary.ready'));
    expect(value.saved).toBe(false);
    expect(value.percent).toBe(96);
    expect(advancePlanningProgress(value, { type: 'failed' }).percent).toBe(96);
    value = advancePlanningProgress(value, done('trip.saved'));
    expect(value.percent).toBe(100);
    expect(value.label).toContain('saved');
  });
});
