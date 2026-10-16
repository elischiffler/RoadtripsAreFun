import { describe, expect, it } from 'vitest';
import {
  INTERESTS,
  PLACES,
  newSetupDraft,
  normalizeWeights,
  preferenceWeights,
  restoreDraft,
  roomInputs,
  setupErrors,
  setupMessage,
  weightsAcknowledged,
} from '../pages/TripSetup/setupModel';

describe('trip setup contract', () => {
  it('maps explicit answers to the complete backend vocabulary and reverses skipped ratings', () => {
    const draft = newSetupDraft();
    const baseline = preferenceWeights(draft);
    expect(Object.keys(baseline)).toEqual(Object.keys(INTERESTS));
    expect(Object.values(baseline).reduce((a, b) => a + b, 0)).toBeCloseTo(1);
    draft.interests = ['nature'];
    draft.ratings[PLACES[0].id] = { rating: 5, reasons: ['nature'] };
    const rated = preferenceWeights(draft);
    expect(rated.nature).toBeGreaterThan(preferenceWeights({ ...draft, ratings: {} }).nature);
    expect(rated.nature).toBeGreaterThan(rated.food);
    expect(rated.hiking_outdoors).toEqual(rated.food);
    draft.ratings[PLACES[0].id] = { rating: null, reasons: [], skipped: true };
    expect(preferenceWeights(draft)).toEqual(preferenceWeights({ ...draft, ratings: {} }));
    draft.ratings[PLACES[0].id] = { rating: 1, reasons: ['nature'] };
    expect(preferenceWeights(draft).nature).toBeLessThan(rated.nature);
    draft.ratings[PLACES[0].id] = { rating: 5, reasons: ['unknown'] };
    expect(preferenceWeights(draft)).toEqual(preferenceWeights({ ...draft, ratings: {} }));
  });
  it('rejects invalid or partial vectors without inventing a profile', () => {
    const zero = Object.fromEntries(Object.keys(INTERESTS).map((key) => [key, 0]));
    expect(() => normalizeWeights(zero)).toThrow(/above zero/);
    expect(() => normalizeWeights({ nature: 1 })).toThrow(/valid/);
    expect(() => normalizeWeights({ ...zero, nature: Infinity })).toThrow(/valid/);
    expect(() => normalizeWeights({ ...zero, nature: -1 })).toThrow(/valid/);
    expect(() => normalizeWeights({ ...zero, nature: true })).toThrow(/valid/);
    expect(
      preferenceWeights({ ...newSetupDraft(), customWeights: { ...zero, nature: 3 } }).nature
    ).toBe(1);
    expect(setupErrors({ ...newSetupDraft(), customWeights: zero }, 2).interests).toMatch(
      /above zero/
    );
  });
  it('validates inputs, room allocations and daily times before sending', () => {
    const draft = newSetupDraft();
    expect(Object.keys(setupErrors(draft, 0))).toEqual(['start', 'destination', 'date']);
    Object.assign(draft, {
      start: 'Boulder',
      destination: 'Boulder',
      date: '2027-06-01',
      time: '',
      stops: '0',
    });
    expect(setupErrors(draft, 0)).toHaveProperty('destination');
    expect(setupErrors(draft, 0)).toHaveProperty('time');
    expect(setupErrors(draft, 0)).toHaveProperty('stops');
    draft.rooms = [{ adults: '2', children: '5, 8' }];
    draft.travelers = '4';
    expect(roomInputs(draft)).toEqual([{ adults: 2, child_ages: [5, 8] }]);
    expect(setupErrors(draft, 1)).toEqual({});
    draft.travelers = '3';
    expect(setupErrors(draft, 1).rooms).toMatch(/add up/);
    draft.rooms[0].children = '5,';
    expect(setupErrors(draft, 1).rooms).toMatch(/separated/);
    draft.rooms[0].children = '18';
    draft.budget = '-1';
    draft.travelers = '0';
    expect(Object.keys(setupErrors(draft, 1))).toEqual(['travelers', 'budget', 'rooms']);
    expect(setupErrors(draft, 3).carStatus).toBeDefined();
    draft.carStatus = 'provided';
    expect(Object.keys(setupErrors(draft, 3))).toEqual(['make', 'model', 'year']);
    Object.assign(draft, { make: 'Toyota', model: 'Corolla', year: '2020' });
    expect(setupErrors(draft, 3)).toEqual({});
    draft.schedule.preferred_hotel_arrival = '22:00';
    expect(setupErrors(draft, 3).schedule).toMatch(/before/);
    draft.schedule.morning_restart = '';
    expect(setupErrors(draft, 3).schedule).toMatch(/valid/);
  });
  it('sends only through the existing chat message contract and checks authoritative weights', () => {
    const draft = {
      ...newSetupDraft(),
      start: ' Boulder ',
      destination: 'Denver',
      date: '2027-06-01',
      carStatus: 'provided',
      year: '2020',
      make: 'Toyota',
      model: 'Corolla',
      interests: ['food'],
    };
    const message = setupMessage(draft);
    const [detailsText, weightsText] = message
      .split('Trip details: ')[1]
      .split('\nTrip-only persona_weights: ');
    const details = JSON.parse(detailsText),
      weights = JSON.parse(weightsText);
    expect(details.start_address).toBe('Boulder');
    expect(details.car_year).toBe(2020);
    expect(details.hotel_rooms).toEqual([{ adults: 1, child_ages: [] }]);
    expect(weights).toEqual(preferenceWeights(draft));
    expect(message).toMatch(/Do not plan yet/);
    expect(message).toMatch(/Do not change my account/);
    expect(
      weightsAcknowledged({ ok: true, tripProfile: { persona_weights: weights } }, weights)
    ).toBe(true);
    expect(
      weightsAcknowledged(
        { ok: true, tripProfile: { persona_weights: preferenceWeights(newSetupDraft()) } },
        weights
      )
    ).toBe(false);
    expect(
      weightsAcknowledged(
        {
          ok: true,
          tripProfile: { persona_weights: weights },
          validationIssues: { budget: 'Invalid' },
        },
        weights
      )
    ).toBe(false);
    expect(weightsAcknowledged({ ok: true, tripProfile: {} }, weights)).toBe(false);
    expect(weightsAcknowledged(false, weights)).toBe(false);
  });
  it('restores versioned drafts and rejects corrupt storage', () => {
    const draft = newSetupDraft();
    const encode = (changes = {}) => JSON.stringify({ version: 1, draft, step: 2, ...changes });
    expect(restoreDraft(encode())).toEqual({ draft, step: 2 });
    expect(restoreDraft(encode({ step: 99 })).step).toBe(0);
    for (const value of [
      'broken',
      'null',
      encode({ version: 0 }),
      encode({ draft: {} }),
      encode({ draft: { ...draft, start: 4 } }),
      encode({ draft: { ...draft, rooms: [] } }),
      encode({ draft: { ...draft, interests: ['unknown'] } }),
      encode({ draft: { ...draft, ratings: { bad: { rating: 4, reasons: [] } } } }),
    ])
      expect(restoreDraft(value)).toBeNull();
  });
});
