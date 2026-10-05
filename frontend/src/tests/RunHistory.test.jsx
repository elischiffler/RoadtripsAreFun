import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import RunHistory from '../pages/AlgorithmLab/RunHistory';
import { getLabRuns } from '../services/algorithmLab';

vi.mock('../services/algorithmLab', () => ({
  getLabRuns: vi.fn(),
  labError: () => 'History unavailable',
}));
beforeEach(() => vi.resetAllMocks());
it('shows persisted measurements and uses the server history cursor', async () => {
  getLabRuns.mockResolvedValueOnce({
    runs: [
      {
        id: 'run-1',
        preset_id: 'short-day',
        mode: 'replay',
        started_at: '2026-10-05T12:00:00Z',
        status: 'completed',
        input: { budget: 180 },
        metrics: {
          cohort_key: 'cohort',
          objective_score: 1200,
          latency_ms: { total: 7.5 },
          external_calls: { mapbox: 0 },
          feasibility: null,
        },
      },
    ],
    groups: [
      {
        cohort_key: 'cohort',
        runs: 3,
        deterministic_observed: true,
        objective: { mean: 1200, stddev: 0 },
      },
    ],
    next_offset: 50,
  });
  getLabRuns.mockResolvedValue({ runs: [], groups: [], next_offset: null });
  render(<RunHistory revision={0} />);
  expect(await screen.findByText('short-day')).toBeInTheDocument();
  expect(screen.getByText('7.5 ms')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Inspect'));
  expect(screen.getByText(/Nightly-target feasibility: Unassessed/)).toBeInTheDocument();
  expect(screen.getByText(/3 comparable run/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Older runs' }));
  await screen.findByText(/Showing 0 runs from 51/);
  expect(getLabRuns.mock.calls[1][1]).toBe(50);
});
it('reports history outages without inventing empty history', async () => {
  getLabRuns.mockRejectedValue(new Error('offline'));
  render(<RunHistory revision={0} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('History unavailable');
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
});
