import { beforeEach, expect, it, vi } from 'vitest';
import request from '../services/protectedRequest';
import { alternativeRequest, loadRouteAlternatives } from '../services/routeAlternatives';
vi.mock('../services/protectedRequest', () => ({ default: { post: vi.fn() } }));
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv('VITE_BACKEND_SERVER', 'http://fixture/');
});
it('samples at most eight actual route positions and converts GeoJSON longitude/latitude once', () => {
  const route = {
    geometry: { coordinates: Array.from({ length: 30 }, (_, i) => [-120 + i / 10, 37 + i / 10]) },
    stops: [{ id: 'provider:1' }, { provider_id: 'provider:1' }],
  };
  const body = alternativeRequest(route);
  expect(body.points).toHaveLength(8);
  expect(body.points[0]).toEqual([37, -120]);
  expect(body.points.at(-1)).toEqual([39.9, -117.1]);
  expect(body.exclude_ids).toEqual(['provider:1']);
});
it('uses coordinate-valid saved stops when a legacy route has no geometry', () => {
  expect(
    alternativeRequest({
      stops: [{ coordinates: [37, -120] }, { coordinates: [91, 0] }, { coordinates: [37, -120] }],
    }).points
  ).toEqual([[37, -120]]);
});
it('uses the authenticated transport, retains source evidence and skips malformed results', async () => {
  const place = {
    id: 'overture:1',
    name: 'Park',
    coordinates: [37, -120],
    source_attribution: 'Overture Maps Foundation',
    source_release: 'fixture',
    source_provenance: [{ dataset: 'fixture' }],
  };
  request.post.mockResolvedValue({
    data: { places: [place, { id: 'invalid', coordinates: [0, 91] }], notice: 'Unscheduled ideas' },
  });
  const controller = new AbortController();
  expect(await loadRouteAlternatives({ stops: [place] }, controller.signal)).toEqual({
    places: [place],
    notice: 'Unscheduled ideas',
  });
  expect(request.post).toHaveBeenCalledWith(
    'http://fixture/route-alternatives',
    { points: [[37, -120]], exclude_ids: ['overture:1'] },
    { signal: controller.signal }
  );
});
it('does not call a provider without coordinates and propagates unavailable responses', async () => {
  await expect(loadRouteAlternatives({})).rejects.toThrow('no locations');
  expect(request.post).not.toHaveBeenCalled();
  request.post.mockRejectedValue(new Error('unavailable'));
  await expect(loadRouteAlternatives({ stops: [{ coordinates: [37, -120] }] })).rejects.toThrow(
    'unavailable'
  );
});
