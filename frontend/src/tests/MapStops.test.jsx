import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import mapboxgl from 'mapbox-gl';
import Map from '../components/Map';

vi.mock('mapbox-gl', () => ({
  default: {
    Map: vi.fn(function ({ container }) {
      this.container = container;
      this.on = vi.fn();
      this.addControl = vi.fn();
      this.remove = vi.fn();
      this.getSource = vi.fn();
      this.getLayer = vi.fn();
      this.addSource = vi.fn();
      this.addLayer = vi.fn();
      this.fitBounds = vi.fn();
      this.easeTo = vi.fn();
    }),
    AttributionControl: vi.fn(),
    Marker: vi.fn(function ({ element }) {
      element.setAttribute('role', 'img');
      this.setLngLat = vi.fn().mockReturnThis();
      this.addTo = vi.fn((map) => {
        map.container.append(element);
        return this;
      });
      this.remove = vi.fn(() => element.remove());
    }),
    Popup: vi.fn(function () {
      const element = document.createElement('div');
      let close;
      this.on = vi.fn((name, callback) => {
        if (name === 'close') close = callback;
        return this;
      });
      this.setDOMContent = vi.fn((content) => {
        element.replaceChildren(content);
        return this;
      });
      this.setLngLat = vi.fn().mockReturnThis();
      this.addTo = vi.fn((map) => {
        map.container.append(element);
        return this;
      });
      this.getElement = () => element;
      this.isOpen = () => element.isConnected;
      this.remove = vi.fn(() => {
        element.remove();
        close?.();
        return this;
      });
    }),
  },
}));

const stops = [
  {
    name: 'Forest walk',
    type: 'stop',
    coordinates: [37.4, -122.1],
    address: 'Trailhead road',
    source_release: '2026-09-23.1',
    source_attribution: 'Overture Maps Foundation',
  },
  { name: 'Coastal hotel', type: 'hotel', coordinates: [36.8, -121.9] },
  { name: 'Missing coordinates', type: 'stop' },
  { name: '<img src=x onerror=alert(1)>', type: 'stop', coordinates: [36.7, -121.8] },
];
function trip(nextStops = stops) {
  return {
    startConfirmed: { latitude: 37.77, longitude: -122.42 },
    endConfirmed: { latitude: 36.6, longitude: -121.9 },
    route: {
      duration: 9000,
      geometry: {
        coordinates: [
          [-122.42, 37.77],
          [-121.9, 36.6],
        ],
      },
      stops: nextStops,
    },
  };
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv('VITE_LOCAL_JOURNEY', 'false');
  vi.stubEnv('VITE_MAPBOX_TOKEN', 'fixture-map-token');
});
afterEach(() => vi.unstubAllEnvs());

it('uses numbered, accessible pins at converted stop coordinates with one safe popup', async () => {
  render(<Map UserChatData={trip()} />);
  const map = mapboxgl.Map.mock.results[0].value;
  map.on.mock.calls.find(([event]) => event === 'load')[1]();
  expect(map.fitBounds).toHaveBeenCalledWith(
    [
      [-122.42, 36.6],
      [-121.8, 37.77],
    ],
    { padding: 32, maxZoom: 12, duration: 0 }
  );
  expect(mapboxgl.Marker).toHaveBeenCalledTimes(3);
  expect(mapboxgl.Marker.mock.results[0].value.setLngLat).toHaveBeenCalledWith([-122.1, 37.4]);
  const first = screen.getByRole('button', { name: 'Stop 1: Forest walk' });
  await userEvent.click(first);
  expect(screen.getByRole('dialog')).toHaveTextContent('Forest walkTrailhead road');
  expect(screen.getByRole('dialog')).not.toHaveTextContent('Source release: 2026-09-23.1');
  expect(screen.queryByRole('link', { name: 'Sources' })).not.toBeInTheDocument();
  expect(screen.getByRole('dialog')).not.toHaveTextContent('Source: Overture Maps Foundation');
  expect(first).toHaveAttribute('aria-expanded', 'true');
  await userEvent.click(screen.getByRole('button', { name: 'Stop 2: Coastal hotel' }));
  expect(screen.getAllByRole('dialog')).toHaveLength(1);
  expect(screen.getByRole('dialog')).toHaveTextContent('Coastal hotel');
  expect(first).toHaveAttribute('aria-expanded', 'false');
  const hostile = screen.getByRole('button', { name: 'Stop 4: <img src=x onerror=alert(1)>' });
  hostile.focus();
  await userEvent.keyboard('{Enter}');
  expect(screen.getByRole('dialog')).toHaveTextContent('<img src=x onerror=alert(1)>');
  expect(screen.getByRole('dialog').querySelector('img')).toBeNull();
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(hostile).toHaveFocus();
});

it('ignores unusable coordinates and clears pins and popups on route change and unmount', async () => {
  const view = render(
    <Map
      UserChatData={trip([
        ...stops,
        null,
        { coordinates: [91, 10] },
        { coordinates: [10, 181] },
        { coordinates: [NaN, 10] },
        { coordinates: ['37', -122] },
      ])}
    />
  );
  expect(mapboxgl.Marker).toHaveBeenCalledTimes(3);
  const markers = mapboxgl.Marker.mock.results.map(({ value }) => value);
  await userEvent.click(screen.getByRole('button', { name: 'Stop 1: Forest walk' }));
  view.rerender(<Map UserChatData={trip([stops[1]])} />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Stop 1: Forest walk' })).not.toBeInTheDocument();
  for (const marker of markers) expect(marker.remove).toHaveBeenCalledOnce();
  view.unmount();
  expect(mapboxgl.Marker.mock.results.at(-1).value.remove).toHaveBeenCalledOnce();
});

it('supports clickable and keyboard pins in the local map without opening Mapbox', async () => {
  vi.stubEnv('VITE_LOCAL_JOURNEY', 'true');
  render(<Map UserChatData={trip()} />);
  expect(mapboxgl.Map).not.toHaveBeenCalled();
  expect(screen.getByText('Local fixture · route schematic')).toBeInTheDocument();
  const pin = screen.getByRole('button', { name: 'Stop 1: Forest walk' });
  pin.focus();
  await userEvent.keyboard(' ');
  expect(screen.getByRole('dialog', { name: 'Stop 1' })).toHaveTextContent('Forest walk');
  await userEvent.click(screen.getByRole('button', { name: 'Close location' }));
  expect(pin).toHaveFocus();
  await userEvent.keyboard('{Enter}');
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Stop 2: Coastal hotel' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('Coastal hotel');
});

it('shows a clear map configuration fallback without creating a provider map', () => {
  vi.stubEnv('VITE_MAPBOX_TOKEN', '');
  render(<Map UserChatData={trip()} />);
  expect(mapboxgl.Map).not.toHaveBeenCalled();
  expect(screen.getByRole('status')).toHaveTextContent('access token is not configured');
});

it('shows a provider load error and retains a clear itinerary path', () => {
  render(<Map UserChatData={trip()} />);
  const map = mapboxgl.Map.mock.results[0].value;
  fireEvent.error(screen.getByRole('button', { name: 'Stop 1: Forest walk' }));
  act(() => map.on.mock.calls.find(([event]) => event === 'error')[1]());
  expect(screen.getByRole('status')).toHaveTextContent('map could not be loaded');
});

it('adds distinct nearby pins and centers a selected actual idea without changing scheduled stops', async () => {
  const idea = {
    id: 'idea:1',
    name: 'Gallery',
    coordinates: [37.5, -122.2],
    source_attribution: 'Fixture catalog',
    place_context: { summary: 'Small galleries with local history exhibits.' },
  };
  const select = vi.fn();
  const data = trip();
  const suggestions = [idea];
  const view = render(
    <Map UserChatData={data} suggestions={suggestions} onSelectSuggestion={select} />
  );
  const pin = screen.getByRole('button', { name: 'Nearby idea: Gallery' });
  await userEvent.click(pin);
  expect(select).toHaveBeenCalledWith(idea);
  expect(mapboxgl.Marker.mock.results.at(-1).value.setLngLat).toHaveBeenCalledWith([-122.2, 37.5]);
  view.rerender(
    <Map
      UserChatData={data}
      suggestions={suggestions}
      selectedSuggestion={idea}
      onSelectSuggestion={select}
    />
  );
  expect(mapboxgl.Map.mock.results[0].value.easeTo).toHaveBeenCalledWith({
    center: [-122.2, 37.5],
    zoom: 12,
    duration: 0,
  });
  expect(screen.getByRole('region', { name: 'Selected nearby idea' })).toHaveTextContent(
    'Unscheduled idea'
  );
  expect(screen.getByRole('region', { name: 'Selected nearby idea' })).toHaveTextContent(
    'Small galleries with local history exhibits.'
  );
  expect(screen.queryByText(/Source: Fixture catalog/)).not.toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: /^Stop / })).toHaveLength(3);
  expect(data.route.stops).toEqual(stops);
});
it('renders local fixture nearby pins with keyboard selection', async () => {
  vi.stubEnv('VITE_LOCAL_JOURNEY', 'true');
  const idea = { id: 'idea:1', name: 'Gallery', coordinates: [37.5, -122.2] };
  const select = vi.fn();
  render(<Map UserChatData={trip()} suggestions={[idea]} onSelectSuggestion={select} />);
  screen.getByRole('button', { name: 'Nearby idea: Gallery' }).focus();
  await userEvent.keyboard('{Enter}');
  expect(select).toHaveBeenCalledWith(idea);
  expect(mapboxgl.Map).not.toHaveBeenCalled();
});

it('joins reviewed context from the route map without annotating source stop dictionaries', async () => {
  const data = trip();
  data.route.stops = structuredClone(data.route.stops);
  data.route.stops[0].provider_id = 'boulder:250';
  data.route.place_context = { 'boulder:250': { summary: 'A trailhead with picnic facilities.' } };
  const original = structuredClone(data.route);
  render(<Map UserChatData={data} />);
  await userEvent.click(screen.getByRole('button', { name: 'Stop 1: Forest walk' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('A trailhead with picnic facilities.');
  expect(data.route).toEqual(original);
});
