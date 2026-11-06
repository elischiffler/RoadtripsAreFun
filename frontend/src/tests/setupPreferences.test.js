import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import process from 'node:process';
import { describe, expect, it } from 'vitest';
import {
  COMPARISONS,
  INTERESTS,
  PLACES,
  STEPS,
  newSetupDraft,
  normalizeWeights,
  preferenceProfiles,
  preferenceWeights,
  restoreDraft,
} from '../pages/TripSetup/setupModel';

const dimensions = Object.keys(INTERESTS);
const vector = (value) => Object.fromEntries(dimensions.map((key) => [key, value]));
const answer = (choice, pair = COMPARISONS[0]) => ({ [pair.id]: choice });
const assertProfile = (profile) => {
  expect(Object.keys(profile)).toEqual(dimensions);
  expect(Object.values(profile).every((value) => Number.isFinite(value) && value >= 0)).toBe(true);
  expect(Object.values(profile).reduce((sum, value) => sum + value, 0)).toBeCloseTo(1, 14);
};

describe('reviewed preference comparison examples', () => {
  it('retains exact reviewed source vectors, factual identity, attribution and snapshot provenance', () => {
    const bytes = readFileSync(
      resolve(process.cwd(), '../docs/data/catalog-pilot-600-20261021/personas.json')
    );
    const source = JSON.parse(bytes);
    const checksum = createHash('sha256').update(bytes).digest('hex');
    expect(COMPARISONS).toHaveLength(3);
    expect(new Set(COMPARISONS.map((pair) => pair.id)).size).toBe(COMPARISONS.length);
    for (const pair of COMPARISONS) {
      for (const place of [pair.left, pair.right]) {
        const reviewed = source.find((record) => record.source_id === place.id);
        expect(reviewed).toBeDefined();
        const profile = reviewed.location_profile;
        expect(place.attribute_ratings).toEqual(profile.attribute_ratings);
        for (const key of ['name', 'description', 'url', 'source_release'])
          expect(place[key]).toBe(profile[key]);
        expect(place.profile_sha256).toBe(checksum);
        expect(place.profile_schema).toBe(reviewed.schema_version);
        expect(place.source_attribution).toBe(profile.source_provenance[0].source_attribution);
        expect(place.ratings_source).toBe(profile.provenance.ratings_source);
        expect(place.ratings_source).toMatch(/inferences.*unknown attributes use 0.5/);
        expect(place.profile_basis).toBe(reviewed.inferred_traveler_fit.basis);
        expect(place.profile_source).toBe('docs/data/catalog-pilot-600-20261021/personas.json');
        expect(place.source_receipts.length).toBeGreaterThan(0);
        for (const receipt of place.source_receipts) {
          expect(receipt).toEqual({
            source_url: expect.stringMatching(/^https:\/\//),
            snapshot_sha256: expect.stringMatching(/^[a-f0-9]{64}$/),
            checked_at: expect.any(String),
          });
          const retained = JSON.stringify(profile.source_provenance);
          expect(retained).toContain(receipt.source_url);
          expect(retained).toContain(receipt.snapshot_sha256);
          expect(retained).toContain(receipt.checked_at);
        }
        assertProfile(normalizeWeights(place.attribute_ratings));
      }
    }
  });
});

describe('two independent per-trip preference profiles', () => {
  it('preserves explicit interests and legacy ratings exactly when no comparisons are answered', () => {
    const draft = newSetupDraft();
    draft.interests = ['food'];
    draft.ratings = {
      [PLACES[0].id]: { rating: 5, reasons: ['nature'] },
      [PLACES[1].id]: { rating: 1, reasons: ['scenery'] },
    };
    const expected = normalizeWeights({ ...vector(1), food: 4, nature: 1.5, scenery: 0.5 });
    for (const comparisonAnswers of [{}, answer('unsure')]) {
      const profiles = preferenceProfiles({ ...draft, comparisonAnswers });
      expect(profiles).toEqual({
        stated: expected,
        comparisons: expected,
        combined: expected,
        hasComparisons: false,
      });
      expect(preferenceWeights({ ...draft, comparisonAnswers })).toEqual(expected);
    }
    const legacy = { ...draft };
    delete legacy.comparisonAnswers;
    expect(preferenceWeights(legacy)).toEqual(expected);
  });

  it.each(['left', 'right'])(
    'uses the chosen reviewed %s profile for the second profile',
    (side) => {
      const pair = COMPARISONS[0];
      const profiles = preferenceProfiles({ ...newSetupDraft(), comparisonAnswers: answer(side) });
      expect(profiles.comparisons).toEqual(normalizeWeights(pair[side].attribute_ratings));
      expect(profiles.hasComparisons).toBe(true);
      assertProfile(profiles.comparisons);
      assertProfile(profiles.combined);
    }
  );

  it('blends an extreme manual profile exactly 50/50 and leaves the editable profile intact', () => {
    const customWeights = { ...vector(0), nightlife: 10 };
    const draft = {
      ...newSetupDraft(),
      interests: ['food'],
      customWeights,
      comparisonAnswers: answer('left'),
    };
    const profiles = preferenceProfiles(draft);
    expect(profiles.stated).toEqual({ ...vector(0), nightlife: 1 });
    for (const key of dimensions)
      expect(profiles.combined[key]).toBe((profiles.stated[key] + profiles.comparisons[key]) / 2);
    expect(preferenceWeights(draft)).toEqual(profiles.combined);
    expect(draft.customWeights).toBe(customWeights);
    expect(draft.customWeights.nightlife).toBe(10);
    expect(profiles.combined.nightlife).toBeGreaterThan(0.5);
    assertProfile(profiles.combined);
    expect(preferenceWeights({ ...draft, comparisonAnswers: {} })).toEqual(profiles.stated);
  });

  it('treats either as equal acceptance and neither as rejection of both supported traits', () => {
    const pair = COMPARISONS[0];
    const either = preferenceProfiles({ ...newSetupDraft(), comparisonAnswers: answer('either') });
    const neither = preferenceProfiles({
      ...newSetupDraft(),
      comparisonAnswers: answer('neither'),
    });
    expect(either.comparisons.nature).toBe(either.comparisons.culture_arts);
    expect(either.comparisons.nature).toBeGreaterThan(either.comparisons.food);
    expect(neither.comparisons.nature).toBe(neither.comparisons.culture_arts);
    expect(neither.comparisons.nature).toBeLessThan(neither.comparisons.food);
    const mean = Object.fromEntries(
      dimensions.map((key) => [
        key,
        (pair.left.attribute_ratings[key] + pair.right.attribute_ratings[key]) / 2,
      ])
    );
    expect(either.comparisons).toEqual(normalizeWeights(mean));
    expect(neither.comparisons).toEqual(
      normalizeWeights(Object.fromEntries(dimensions.map((key) => [key, 1 - mean[key]])))
    );
    assertProfile(either.combined);
    assertProfile(neither.combined);
  });

  it('gives answered comparisons equal influence and excludes unsure from the evidence count', () => {
    const draft = {
      ...newSetupDraft(),
      comparisonAnswers: {
        ...answer('left', COMPARISONS[0]),
        ...answer('right', COMPARISONS[1]),
        ...answer('unsure', COMPARISONS[2]),
      },
    };
    const expected = normalizeWeights(
      Object.fromEntries(
        dimensions.map((key) => [
          key,
          (COMPARISONS[0].left.attribute_ratings[key] +
            COMPARISONS[1].right.attribute_ratings[key]) /
            2,
        ])
      )
    );
    expect(preferenceProfiles(draft).comparisons).toEqual(expected);
    const withoutUnsure = { ...draft.comparisonAnswers };
    delete withoutUnsure[COMPARISONS[2].id];
    expect(preferenceWeights(draft)).toEqual(
      preferenceWeights({ ...draft, comparisonAnswers: withoutUnsure })
    );
  });

  it.each([null, [], 'left', { unknown: 'left' }, answer('invalid'), answer(1)])(
    'rejects malformed direct comparison answers %j',
    (comparisonAnswers) => {
      expect(() => preferenceWeights({ ...newSetupDraft(), comparisonAnswers })).toThrow(
        /comparison answers/
      );
    }
  );

  it.each([
    { ...vector(0.5), food: NaN },
    { ...vector(0.5), food: -1 },
    { ...vector(0.5), food: 1.1 },
    { ...vector(0.5), food: '0.5' },
    { ...vector(0.5), invented: 0.5 },
    { food: 0.5 },
    vector(0),
  ])('rejects malformed reviewed vectors before producing any combined values', (invalid) => {
    const place = COMPARISONS[0].left;
    const original = place.attribute_ratings;
    try {
      place.attribute_ratings = invalid;
      expect(() =>
        preferenceProfiles({ ...newSetupDraft(), comparisonAnswers: answer('left') })
      ).toThrow();
    } finally {
      place.attribute_ratings = original;
    }
  });

  it.each([
    { ...vector(1), food: Infinity },
    { ...vector(1), food: -1 },
    { ...vector(1), food: '1' },
    { ...vector(1), invented: 1 },
    vector(0),
  ])('rejects invalid manual vectors even if comparison answers are valid', (customWeights) => {
    expect(() =>
      preferenceWeights({ ...newSetupDraft(), customWeights, comparisonAnswers: answer('left') })
    ).toThrow();
  });
});

describe('version 1 setup draft migration', () => {
  it('adds comparisons without changing legacy answers, manual amounts, step or five-stage order', () => {
    const draft = {
      ...newSetupDraft(),
      start: 'Boulder',
      destination: 'Denver',
      interests: ['nature'],
      customWeights: { ...vector(2), food: 7 },
      ratings: { [PLACES[0].id]: { rating: 5, reasons: ['scenery'] } },
    };
    delete draft.comparisonAnswers;
    const restored = restoreDraft(JSON.stringify({ version: 1, draft, step: 2 }));
    expect(restored).toEqual({ draft: { ...draft, comparisonAnswers: {} }, step: 2 });
    expect(preferenceWeights(restored.draft)).toEqual(normalizeWeights(draft.customWeights));
    expect(STEPS).toEqual([
      'Where and when',
      'People and rooms',
      'What you enjoy',
      'Daily timing',
      'Review',
    ]);
  });

  it('retains unanswered or valid comparison answers across draft restoration', () => {
    const draft = { ...newSetupDraft(), comparisonAnswers: answer('neither') };
    expect(restoreDraft(JSON.stringify({ version: 1, draft, step: 4 }))).toEqual({
      draft,
      step: 4,
    });
  });

  it.each([null, [], { unknown: 'left' }, answer('bad')])(
    'discards only malformed new comparison state while preserving the older trip %j',
    (comparisonAnswers) => {
      const draft = { ...newSetupDraft(), start: 'Keep my city', comparisonAnswers };
      expect(restoreDraft(JSON.stringify({ version: 1, draft, step: 3 }))).toEqual({
        draft: { ...draft, comparisonAnswers: {} },
        step: 3,
      });
    }
  );

  it('preserves zero manual amounts so existing validation can ask the traveler to correct them', () => {
    const draft = { ...newSetupDraft(), customWeights: vector(0) };
    delete draft.comparisonAnswers;
    const restored = restoreDraft(JSON.stringify({ version: 1, draft, step: 2 }));
    expect(restored.draft.customWeights).toEqual(vector(0));
    expect(() => preferenceWeights(restored.draft)).toThrow(/above zero/);
  });

  it('continues rejecting malformed legacy drafts', () => {
    for (const change of [{ ratings: [] }, { schedule: [] }, { interests: ['invented'] }])
      expect(
        restoreDraft(JSON.stringify({ version: 1, draft: { ...newSetupDraft(), ...change } }))
      ).toBeNull();
    const draft = newSetupDraft();
    delete draft.start;
    expect(restoreDraft(JSON.stringify({ version: 1, draft }))).toBeNull();
  });
});
