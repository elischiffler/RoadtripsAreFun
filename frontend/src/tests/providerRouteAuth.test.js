import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { getInitialRoute, getFinalRoute } from '../pages/ChatPage/getRoute';

vi.mock('axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('provider route access token', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    import.meta.env.VITE_BACKEND_SERVER = 'https://api.example.test/';
  });

  it('sends the Cognito access token in the route request header', async () => {
    sessionStorage.setItem('accessToken', 'signed-access-token');
    axios.get.mockResolvedValueOnce({ data: { geometry: {} } });
    await getInitialRoute(1, 2, 3, 4);
    expect(axios.get).toHaveBeenCalledWith('https://api.example.test/get-initial-route', {
      params: { start_lat: 1, start_lon: 2, end_lat: 3, end_lon: 4 },
      headers: { Authorization: 'Bearer signed-access-token' },
    });
  });

  it('sends the same token for the final route POST', async () => {
    sessionStorage.setItem('accessToken', 'signed-access-token');
    axios.post.mockResolvedValueOnce({ data: { stops: [] } });
    await getFinalRoute({ geometry: {} }, 100, 0);
    expect(axios.post).toHaveBeenCalledWith(
      'https://api.example.test/generate-final-route',
      { initial_route: { geometry: {} }, num_stops: 0, budget: 100 },
      { headers: { Authorization: 'Bearer signed-access-token' } }
    );
  });
});
