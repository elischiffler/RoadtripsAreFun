import { expect, it } from 'vitest';
import { itineraryEntries, toggleVisited, visitedStopIds } from '../services/tripPresentation';

const place = (name, extra = {}) => ({ name, time: '10:00 AM', ...extra });
it('keeps visit identities stable across reload and reorder, distinguishing repeated visits', () => {
  const first = [{ date: 'Day 1', stops: [place('Park'), place('Cafe'), place('Park')] }];
  const before = itineraryEntries(first)[0].stops.map((item) => item.id);
  const reordered = JSON.parse(JSON.stringify(first));
  reordered[0].stops = [place('Cafe'), place('Park'), place('Park')];
  const after = itineraryEntries(reordered)[0].stops.map((item) => item.id);
  expect(after).toEqual([before[1], before[0], before[2]]);
  expect(new Set(before).size).toBe(3);
});
it('excludes meal windows and paired departures from explicit visits, and preserves unknown fields', () => {
  const entries = itineraryEntries([
    {
      date: 'Day 1',
      stops: [
        place('Park'),
        place('Leaving', { paired_departure: true }),
        place('Lunch', { kind: 'meal' }),
      ],
    },
  ]);
  expect(entries[0].stops).toHaveLength(1);
  expect(entries[0].meals).toHaveLength(1);
  const presentation = { compact: true, visitedStopIds: ['other', null] };
  const marked = toggleVisited(presentation, entries[0].stops[0].id);
  expect(marked.compact).toBe(true);
  expect(visitedStopIds(marked).size).toBe(2);
  expect(toggleVisited(marked, entries[0].stops[0].id).visitedStopIds).toEqual(['other']);
  expect(presentation.visitedStopIds).toEqual(['other', null]);
});
