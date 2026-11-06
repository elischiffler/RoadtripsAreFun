import { beforeEach, expect, it, vi } from 'vitest';
import request from '../services/protectedRequest';
import { alternativeRequest, loadRouteAlternatives } from '../services/routeAlternatives';
vi.mock('../services/protectedRequest', () => ({ default: { post: vi.fn() } }));
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv('VITE_BACKEND_SERVER', 'http://fixture/');
});
it('sends full GeoJSON for backend distance sampling', () => {
  const route = {
    geometry: { coordinates: Array.from({ length: 30 }, (_, i) => [-120 + i / 10, 37 + i / 10]) },
    stops: [{ id: 'provider:1' }, { provider_id: 'provider:1' }],
  };
  const body = alternativeRequest(route);
  expect(body.geometry).toEqual(route.geometry.coordinates);
  expect(body.geometry).toHaveLength(30);
  expect(body.points).toBeUndefined();
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
    { points: [[37, -120]], exclude_ids: ['overture:1'], exclude_coordinates: [[37, -120]] },
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

it('excludes every current stop by both identifiers and coordinates', () => {
  expect(
    alternativeRequest({
      geometry: {
        coordinates: [
          [-120, 37],
          [-121, 38],
        ],
      },
      stops: [{ id: 'local:1', provider_id: 'catalog:1', coordinates: [37, -120] }],
    })
  ).toMatchObject({ exclude_ids: ['catalog:1', 'local:1'], exclude_coordinates: [[37, -120]] });
});
it('rejects oversized or malformed geometry instead of searching a truncated route', async () => {
  await expect(
    loadRouteAlternatives({
      geometry: { coordinates: Array.from({ length: 10001 }, () => [-120, 37]) },
    })
  ).rejects.toThrow('cannot be searched');
  await expect(
    loadRouteAlternatives({
      geometry: {
        coordinates: [
          [-120, 37],
          ['bad', 38],
          [-121, 38],
        ],
      },
    })
  ).rejects.toThrow('invalid geometry');
  expect(request.post).not.toHaveBeenCalled();
});
