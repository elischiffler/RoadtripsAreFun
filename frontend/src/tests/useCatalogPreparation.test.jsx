import { beforeEach, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import useCatalogPreparation from '../pages/TripSetup/useCatalogPreparation';
import { loadRouteAlternatives } from '../services/routeAlternatives';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
vi.mock('../services/routeAlternatives', () => ({ loadRouteAlternatives: vi.fn() }));
const route = {
  geometry: {
    coordinates: [
      [-105, 40],
      [-104, 41],
    ],
  },
};
function Probe({ value, inputKey }) {
  const state = useCatalogPreparation(value, inputKey);
  return (
    <p>
      {state.status}:{state.places.map((p) => p.name).join(',')}
    </p>
  );
}
Probe.propTypes = { value: () => null, inputKey: () => null };
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  fixtureSession();
});
it('does nothing while typing and caches only bounded read-only catalog results after road geometry', async () => {
  loadRouteAlternatives.mockResolvedValue({ places: [{ name: 'Admitted idea' }] });
  const view = render(<Probe inputKey="typed-address" />);
  expect(loadRouteAlternatives).not.toHaveBeenCalled();
  view.rerender(<Probe value={route} inputKey="source-geometry" />);
  await screen.findByText('ready:Admitted idea');
  view.rerender(<Probe />);
  view.rerender(<Probe value={route} inputKey="source-geometry" />);
  await screen.findByText('ready:Admitted idea');
  expect(loadRouteAlternatives).toHaveBeenCalledTimes(1);
});
it('aborts changed input and suppresses late old-route and old-account ideas', async () => {
  let finish;
  loadRouteAlternatives
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    )
    .mockResolvedValue({ places: [{ name: 'Current idea' }] });
  const view = render(<Probe value={route} inputKey="old" />);
  await waitFor(() => expect(loadRouteAlternatives).toHaveBeenCalledTimes(1));
  const signal = loadRouteAlternatives.mock.calls[0][1];
  view.rerender(<Probe value={route} inputKey="new" />);
  expect(signal.aborted).toBe(true);
  await screen.findByText('ready:Current idea');
  await act(async () => finish({ places: [{ name: 'Stale idea' }] }));
  expect(screen.queryByText(/Stale idea/)).not.toBeInTheDocument();
  act(() => signOut());
  expect(screen.queryByText(/Current idea/)).not.toBeInTheDocument();
});
