import { expect, it, vi } from 'vitest';
import {
  preparationRequest,
  tentativeAreas,
  preparationPlaces,
} from '../services/routePreparation';
vi.mock('../services/tripRouteStream', () => ({ streamRoutePreparation: vi.fn() }));
const route = {
  duration: 7200,
  geometry: {
    coordinates: [
      [-105, 40],
      [-104, 41],
    ],
  },
};
it('requires known finite road geometry and a valid departure clock', () => {
  expect(preparationRequest(null, { time: '09:00' })).toBeNull();
  expect(preparationRequest(route, { time: '24:00' })).toBeNull();
  expect(preparationRequest({ ...route, duration: Infinity }, { time: '09:00' })).toBeNull();
  expect(
    preparationRequest(
      {
        ...route,
        geometry: {
          coordinates: [
            [181, 0],
            [0, 0],
          ],
        },
      },
      { time: '09:00' }
    )
  ).toBeNull();
  expect(preparationRequest(route, { time: '09:00', schedule: {} })).toEqual({
    geometry: route.geometry.coordinates,
    driving_seconds: 7200,
    departure_clock: '09:00',
    scheduling_policy: {},
  });
});
it('retains night driving and allows only bounded tentative hints', () => {
  const request = preparationRequest(route, {
    time: '18:00',
    dailyRhythm: { driveStart: 18, driveEnd: 6, sleepStart: 8, sleepEnd: 16 },
  });
  expect(request.scheduling_policy.daily_schedule.slots[0]).toBe('drive');
  const area = {
    id: '1',
    label: 'Area',
    coordinates: [40, -100],
    tentative: true,
    hotel_quotes_checked: false,
    availability_checked: false,
    clock_basis: 'departure_wall_clock_estimate',
  };
  expect(tentativeAreas(Array(20).fill(area))).toHaveLength(3);
  expect(
    tentativeAreas([{ ...area, tentative: false }, { ...area, coordinates: [200, 0] }, {}])
  ).toEqual([]);
  expect(
    preparationPlaces(Array(20).fill({ id: '1', name: 'Idea', coordinates: [40, -100] }))
  ).toHaveLength(12);
});
