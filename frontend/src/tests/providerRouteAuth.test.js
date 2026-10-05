import { fixtureSession } from './sessionFixtures';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { getInitialRoute, getFinalRoute, getRoutingAlgorithm } from '../pages/ChatPage/getRoute';

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('provider route access token', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    fixtureSession();
    localStorage.clear();
    import.meta.env.VITE_BACKEND_SERVER = 'https://api.example.test/';
  });

  it('sends the Cognito access token in the route request header', async () => {
    axios.get.mockResolvedValueOnce({ data: { geometry: {} } });
    await getInitialRoute(1, 2, 3, 4);
    expect(axios.get).toHaveBeenCalledWith('https://api.example.test/get-initial-route', {
      params: { start_lat: 1, start_lon: 2, end_lat: 3, end_lon: 4 },
      headers: {
        Authorization: `Bearer ${sessionStorage.getItem('accessToken')}`,
        'X-Cognito-Id-Token': sessionStorage.getItem('idToken'),
      },
    });
  });

  it('sends the same token for the final route POST', async () => {
    axios.post.mockResolvedValueOnce({ data: { stops: [] } });
    await getFinalRoute({ geometry: {} }, 100, 0);
    expect(axios.post).toHaveBeenCalledWith(
      'https://api.example.test/generate-final-route',
      {
        initial_route: { geometry: {} },
        num_stops: 0,
        budget: 100,
        traveler_count: null,
        hotel_rooms: null,
      },
      {
        headers: {
          Authorization: `Bearer ${sessionStorage.getItem('accessToken')}`,
          'X-Cognito-Id-Token': sessionStorage.getItem('idToken'),
        },
      }
    );
  });

  it('clears a retired algorithm choice before requesting a route', async () => {
    localStorage.setItem('devRoutingAlgorithm', 'greedy');
    axios.post.mockResolvedValueOnce({ data: { stops: [] } });
    await getFinalRoute({ geometry: {} }, 100, 0, null, '2026-10-01T09:00:00');
    expect(getRoutingAlgorithm()).toBeNull();
    expect(axios.post.mock.calls[0][1]).toEqual({
      initial_route: { geometry: {} },
      num_stops: 0,
      budget: 100,
      traveler_count: null,
      hotel_rooms: null,
      start: '2026-10-01T09:00:00',
    });
  });
  it('forwards explicit family room allocation without changing budget or identity', async () => {
    const rooms = [
      { adults: 2, child_ages: [5] },
      { adults: 1, child_ages: [] },
    ];
    axios.post.mockResolvedValueOnce({ data: { stops: [] } });
    await getFinalRoute({ geometry: {} }, 100, 0, null, '2030-01-01T09:00:00Z', 4, rooms);
    expect(axios.post.mock.calls[0][1]).toMatchObject({
      traveler_count: 4,
      hotel_rooms: rooms,
      budget: 100,
    });
    expect(axios.post.mock.calls[0][2].headers.Authorization).toBe(
      `Bearer ${sessionStorage.getItem('accessToken')}`
    );
  });
});
