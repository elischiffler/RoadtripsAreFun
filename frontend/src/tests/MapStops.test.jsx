import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Map from '../components/Map';
import request from '../services/protectedRequest';
import { loadAppleMaps } from '../services/appleMaps';

vi.mock('../services/appleMaps', async (original) => ({
  ...(await original()),
  loadAppleMaps: vi.fn(),
}));
vi.mock('../services/protectedRequest', async (original) => ({
  ...(await original()),
  default: { post: vi.fn() },
}));

const coordinates = [
  [37.77, -122.42],
  [37.4, -122.1],
  [36.6, -121.9],
];
const points = coordinates.map(([lat, lon]) => [lon, lat]);
const route = {
  coordinates,
  geometry: { type: 'LineString', coordinates: points },
  stops: [
    {
      name: 'Forest walk',
      type: 'stop',
      coordinates: coordinates[1],
      source_attribution: 'Fixture catalog',
    },
    { name: 'Missing coordinates', type: 'stop' },
    { name: '<img src=x onerror=alert(1)>', type: 'hotel', coordinates: [36.8, -121.9] },
  ],
};
const idea = { id: 'idea:1', name: 'Gallery', coordinates: [37.5, -122.2] };
const journey = { route };

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv('VITE_LOCAL_JOURNEY', 'false');
  vi.stubEnv('VITE_APPLE_MAPS_TOKEN', 'public-mapkit-fixture');
  loadAppleMaps.mockResolvedValue({
    Map: vi.fn(function (host) {
      this.addItems = (items) =>
        items.forEach((item) => {
          if (item.factory) {
            item.element = item.factory();
            host.append(item.element);
          }
        });
      this.removeItems = (items) => items.forEach((item) => item.element?.remove());
      this.showItems = vi.fn();
      this.destroy = () => host.replaceChildren();
    }),
    Coordinate: vi.fn(function (latitude, longitude) {
      Object.assign(this, { latitude, longitude });
    }),
    PolylineOverlay: vi.fn(function (points) {
      this.points = points;
    }),
    Annotation: vi.fn(function (coordinate, factory) {
      Object.assign(this, { coordinate, factory });
    }),
    Padding: vi.fn(function () {}),
    Style: vi.fn(function () {}),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
});
afterEach(() => vi.unstubAllEnvs());

it('uses Apple as the basemap for legacy geometry, retaining the original directions credit', async () => {
  const select = vi.fn();
  render(<Map UserChatData={journey} suggestions={[idea]} onSelectSuggestion={select} />);
  const pin = await screen.findByRole('button', { name: 'Stop 1: Forest walk' });
  await userEvent.click(pin);
  expect(screen.getByRole('status')).toHaveTextContent('Fixture catalog');
  expect(screen.getByText('Directions © Mapbox')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Stop 2: Missing coordinates' })).toBeNull();
  expect(screen.getByRole('button', { name: /Stop 3: <img/ })).toBeVisible();
  expect(document.querySelector('img[src="x"]')).toBeNull();
  await userEvent.click(screen.getByRole('button', { name: 'Nearby idea: Gallery' }));
  expect(select).toHaveBeenCalledWith(idea);
  expect(request.post).not.toHaveBeenCalled();
});

it('refreshes Apple directions in memory after an outage and never adds a legacy credit', async () => {
  request.post.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({
    data: { directions_provider: 'apple', geometry: route.geometry },
  });
  const intent = { ...route, directions_provider: 'apple', geometry: undefined };
  render(<Map UserChatData={{ route: intent }} />);
  expect(await screen.findByText(/Your itinerary is still available/)).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Retry directions' }));
  await screen.findByRole('button', { name: 'Stop 1: Forest walk' });
  expect(request.post).toHaveBeenCalledTimes(2);
  expect(request.post.mock.calls[1][0]).toMatch(/route-directions$/);
  expect(request.post.mock.calls[1][1]).toEqual({ coordinates });
  expect(screen.queryByText('Directions © Mapbox')).toBeNull();
  expect(intent.geometry).toBeUndefined();
});

it('does not render Apple line data on a non-Apple fallback', async () => {
  vi.stubEnv('VITE_APPLE_MAPS_TOKEN', '');
  render(<Map UserChatData={{ route: { ...route, directions_provider: 'apple' } }} />);
  expect(screen.getByText(/Apple Maps directions are unavailable/)).toBeVisible();
  expect(document.querySelector('polyline')).toBeNull();
  expect(loadAppleMaps).not.toHaveBeenCalled();
});

it('renders local fixture nearby pins with keyboard selection', async () => {
  vi.stubEnv('VITE_LOCAL_JOURNEY', 'true');
  const select = vi.fn();
  render(<Map UserChatData={journey} suggestions={[idea]} onSelectSuggestion={select} />);
  const pin = screen.getByRole('button', { name: 'Nearby idea: Gallery' });
  pin.focus();
  await userEvent.keyboard('{Enter}');
  await waitFor(() => expect(select).toHaveBeenCalledWith(idea));
  expect(screen.getByText('Local fixture · route schematic')).toBeVisible();
  expect(loadAppleMaps).not.toHaveBeenCalled();
});
