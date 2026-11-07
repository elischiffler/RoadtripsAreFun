import { loadRoutePreparation } from '../services/routePreparation';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import RouteEstimate from '../pages/TripSetup/RouteEstimate';
import { estimateStructuredRoute, resolveTripLocation } from '../services/tripPlanner';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
vi.mock('../services/tripPlanner', () => ({
  estimateStructuredRoute: vi.fn(),
  resolveTripLocation: vi.fn(),
  plannerError: () => 'Could not check this drive.',
}));
vi.mock('../services/routePreparation', async (importOriginal) => ({
  ...(await importOriginal()),
  loadRoutePreparation: vi.fn(async () => ({ places: [], catalog_status: 'ready' })),
}));
const start = { address: 'Denver, Colorado', latitude: 39.7, longitude: -105 };
const end = { address: 'Boulder, Colorado', latitude: 40, longitude: -105.2 };
beforeEach(() => {
  vi.resetAllMocks();
  loadRoutePreparation.mockResolvedValue({ places: [] });
  sessionStorage.clear();
  fixtureSession();
  estimateStructuredRoute.mockResolvedValue({
    duration: 3600,
    distance: 16093.44,
    geometry: {
      coordinates: [
        [-105, 39.7],
        [-105.2, 40],
      ],
    },
  });
});
it('does not guess ambiguous provider locations and estimates only confirmed choices', async () => {
  resolveTripLocation
    .mockResolvedValueOnce([start, { ...start, address: 'Denver, Iowa' }])
    .mockResolvedValueOnce([end]);
  render(<RouteEstimate start="Denver" destination="Boulder" />);
  await userEvent.click(screen.getByRole('button', { name: 'Estimate driving time' }));
  const confirm = await screen.findByRole('button', { name: 'Use these locations for estimate' });
  expect(confirm).toBeDisabled();
  expect(estimateStructuredRoute).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('radio', { name: 'Denver, Colorado' }));
  await userEvent.click(confirm);
  expect(await screen.findByText(/About 1.0 hours driving/)).toBeInTheDocument();
  expect(estimateStructuredRoute.mock.calls[0].slice(0, 2)).toEqual([start, end]);
  const summary = screen.getByText(/View route · About 1.0 hours driving/);
  expect(summary.closest('details')).not.toHaveAttribute('open');
  await userEvent.click(summary);
  expect(screen.getByLabelText('Trip preview')).toBeInTheDocument();
  expect(screen.getByText(/A · Denver, Colorado/)).toBeInTheDocument();
  expect(screen.getByText(/B · Boulder, Colorado/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Done viewing route' }));
  expect(summary).toHaveFocus();
  expect(summary.closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText(/Driving only, before stops and meals/)).toBeInTheDocument();
});
it('clears estimates on changed text and discards late results after sign out', async () => {
  resolveTripLocation.mockResolvedValueOnce([start]).mockResolvedValueOnce([end]);
  const view = render(<RouteEstimate start="Denver" destination="Boulder" />);
  await userEvent.click(screen.getByRole('button', { name: 'Estimate driving time' }));
  await screen.findByText(/About 1.0 hours driving/);
  view.rerender(<RouteEstimate start="Colorado Springs" destination="Boulder" />);
  expect(screen.queryByText(/About 1.0 hours driving/)).not.toBeInTheDocument();
  let finish;
  resolveTripLocation.mockResolvedValueOnce([start]).mockResolvedValueOnce([end]);
  estimateStructuredRoute.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  await userEvent.click(screen.getByRole('button', { name: 'Estimate driving time' }));
  await waitFor(() => expect(estimateStructuredRoute).toHaveBeenCalledTimes(2));
  act(() => signOut());
  await act(async () => finish({ duration: 7200, distance: 1000 }));
  expect(screen.queryByText('About 2.0 hours driving')).not.toBeInTheDocument();
});

it('aborts a stale estimate when its endpoints change and reports recoverable lookup errors', async () => {
  let finish;
  resolveTripLocation.mockResolvedValueOnce([start]).mockResolvedValueOnce([end]);
  estimateStructuredRoute.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const view = render(<RouteEstimate start="Denver" destination="Boulder" />);
  await userEvent.click(screen.getByRole('button', { name: 'Estimate driving time' }));
  await waitFor(() => expect(estimateStructuredRoute).toHaveBeenCalled());
  const signal = estimateStructuredRoute.mock.calls[0][2];
  view.rerender(<RouteEstimate start="New city" destination="Boulder" />);
  expect(signal.aborted).toBe(true);
  await act(async () => finish({ duration: 7200, distance: 50000 }));
  expect(screen.queryByText('About 2.0 hours driving')).not.toBeInTheDocument();
  resolveTripLocation
    .mockRejectedValueOnce(new Error('lookup unavailable'))
    .mockResolvedValueOnce([end]);
  await userEvent.click(screen.getByRole('button', { name: 'Estimate driving time' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not check this drive.');
  expect(screen.getByRole('button', { name: 'Estimate driving time' })).toBeEnabled();
});
