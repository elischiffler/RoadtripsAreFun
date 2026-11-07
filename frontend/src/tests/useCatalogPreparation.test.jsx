import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import useCatalogPreparation from '../pages/TripSetup/useCatalogPreparation';
import { loadRoutePreparation } from '../services/routePreparation';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
vi.mock('../services/routePreparation', async (importOriginal) => ({
  ...(await importOriginal()),
  loadRoutePreparation: vi.fn(),
}));
const route = {
  duration: 72000,
  geometry: {
    coordinates: [
      [-105, 40],
      [-85, 40],
    ],
  },
};
const draft = { time: '09:00', date: '2035-06-01', schedule: {} };
const place = (name) => ({ id: name, name, coordinates: [40, -100] });
const area = {
  id: 'area:1',
  label: 'Tentative area',
  coordinates: [40, -100],
  tentative: true,
  hotel_quotes_checked: false,
  availability_checked: false,
  clock_basis: 'departure_wall_clock_estimate',
};
const result = (name) => ({
  catalog_status: 'ready',
  places: [place(name)],
  possible_overnight_areas: [area],
  sections_checked: 6,
});
function Probe({ value, inputKey, settings = draft }) {
  const state = useCatalogPreparation(value, inputKey, settings);
  return (
    <p>
      {state.status}:{state.sections}:{state.places.map((p) => p.name).join(',')}:
      {state.areas.length}
    </p>
  );
}
Probe.propTypes = { value: () => null, inputKey: () => null, settings: () => null };
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  fixtureSession();
});
afterEach(() => vi.useRealTimers());
it('does nothing while typing and caches bounded read-only preparation for known roads', async () => {
  loadRoutePreparation.mockResolvedValue(result('Admitted idea'));
  const view = render(<Probe inputKey="typed" />);
  expect(loadRoutePreparation).not.toHaveBeenCalled();
  view.rerender(<Probe value={route} inputKey="road" />);
  await screen.findByText('ready:6:Admitted idea:1');
  view.rerender(<Probe />);
  view.rerender(<Probe value={route} inputKey="road" />);
  await screen.findByText('ready:6:Admitted idea:1');
  expect(loadRoutePreparation).toHaveBeenCalledTimes(1);
});
it('paints partial sections, aborts old input and suppresses late route/account events', async () => {
  let finish;
  loadRoutePreparation
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    )
    .mockResolvedValue(result('Current idea'));
  const view = render(<Probe value={route} inputKey="old" />);
  await waitFor(() => expect(loadRoutePreparation).toHaveBeenCalledTimes(1));
  const [, signal, progress] = loadRoutePreparation.mock.calls[0];
  act(() => {
    progress({ stage: 'preparation.areas', preview_only: true, possible_overnight_areas: [area] });
    progress({
      stage: 'preparation.catalog',
      sections_checked: 2,
      places: [place('Partial idea')],
    });
  });
  expect(screen.getByText('loading:2:Partial idea:1')).toBeInTheDocument();
  view.rerender(<Probe value={route} inputKey="new" />);
  expect(signal.aborted).toBe(true);
  expect(screen.queryByText(/Partial idea/)).not.toBeInTheDocument();
  await screen.findByText('ready:6:Current idea:1');
  await act(async () => {
    progress({ stage: 'preparation.catalog', sections_checked: 6, places: [place('Stale idea')] });
    finish(result('Stale idea'));
  });
  expect(screen.queryByText(/Stale idea/)).not.toBeInTheDocument();
  act(() => signOut());
  expect(screen.queryByText(/Current idea/)).not.toBeInTheDocument();
});
it('debounces rapid clock edits and aborts before a date replacement scan', async () => {
  vi.useFakeTimers();
  loadRoutePreparation.mockImplementation(() => new Promise(() => {}));
  const view = render(<Probe value={route} inputKey="road" />);
  await act(() => vi.advanceTimersByTimeAsync(200));
  view.rerender(<Probe value={route} inputKey="road" settings={{ ...draft, time: '10:00' }} />);
  await act(() => vi.advanceTimersByTimeAsync(200));
  view.rerender(<Probe value={route} inputKey="road" settings={{ ...draft, time: '11:00' }} />);
  await act(() => vi.advanceTimersByTimeAsync(399));
  expect(loadRoutePreparation).not.toHaveBeenCalled();
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(loadRoutePreparation).toHaveBeenCalledTimes(1);
  expect(loadRoutePreparation.mock.calls[0][0].departure_clock).toBe('11:00');
  const signal = loadRoutePreparation.mock.calls[0][1];
  view.rerender(
    <Probe value={route} inputKey="road" settings={{ ...draft, date: '2035-06-02' }} />
  );
  expect(signal.aborted).toBe(true);
  await act(() => vi.advanceTimersByTimeAsync(400));
  expect(loadRoutePreparation).toHaveBeenCalledTimes(2);
});
it('does not cache partial failures or turn malformed area flags into hotel claims', async () => {
  loadRoutePreparation.mockResolvedValue({
    ...result('Idea'),
    catalog_status: 'partial',
    possible_overnight_areas: [{ ...area, availability_checked: true }],
  });
  const view = render(<Probe value={route} inputKey="road" />);
  await screen.findByText('partial:6:Idea:0');
  view.rerender(<Probe />);
  view.rerender(<Probe value={route} inputKey="road" />);
  await waitFor(() => expect(loadRoutePreparation).toHaveBeenCalledTimes(2));
});
