import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import RunHistory from '../pages/AlgorithmLab/RunHistory';
import { getLabRuns, getLabResult } from '../services/algorithmLab';

vi.mock('../services/algorithmLab', () => ({
  getLabRuns: vi.fn(),
  getLabResult: vi.fn(),
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

it('opens a saved trip without generating another provider run', async () => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = vi.fn(function () {
    this.removeAttribute('open');
  });
  getLabRuns.mockResolvedValue({
    runs: [
      {
        id: 'saved-run',
        preset_id: 'coastal-nature',
        status: 'completed',
        has_result: true,
        started_at: '2026-10-05T16:00:00Z',
      },
    ],
    groups: [],
    next_offset: null,
  });
  getLabResult.mockResolvedValue({
    route: { stops: [{ name: 'Saved attraction' }] },
    itinerary: [{ date: '2026-10-06', stops: [{ name: 'Saved visit', time: '11:00' }] }],
  });
  render(<RunHistory revision={0} />);
  fireEvent.click(await screen.findByRole('button', { name: 'View map and itinerary' }));
  expect(await screen.findByText('Saved visit')).toBeInTheDocument();
  expect(getLabResult).toHaveBeenCalledWith('saved-run', expect.any(AbortSignal));
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
  expect(HTMLDialogElement.prototype.close).toHaveBeenCalledOnce();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'View map and itinerary' }));
  await screen.findByText('Saved visit');
  fireEvent.click(screen.getByRole('button', { name: 'Close trip' }));
  expect(HTMLDialogElement.prototype.close).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it('retains the failed stage, provider cause and attempts in history after reload', async () => {
  getLabRuns.mockResolvedValue({
    runs: [
      {
        id: 'failed-run',
        preset_id: 'medium',
        mode: 'live',
        started_at: '2026-10-05T12:00:00Z',
        status: 'failed',
        has_result: false,
        error: {
          stage: 'candidates',
          code: 'provider_or_planning_failure',
          message: 'AI unavailable',
          http_status: 503,
          causes: [{ message: 'Gateway returned HTTP 503' }],
        },
        attempts: [{ attempt: 3, max_attempts: 3, outcome: 'failed' }],
      },
    ],
    groups: [],
    next_offset: null,
  });
  render(<RunHistory revision={0} />);
  await screen.findByText('medium');
  fireEvent.click(screen.getByText('Inspect'));
  expect(screen.getByRole('alert')).toHaveTextContent('candidates: AI unavailable');
  expect(screen.getByText('Gateway returned HTTP 503')).toBeInTheDocument();
  expect(screen.getByLabelText('Error diagnostic')).toHaveTextContent('"attempt": 3');
  expect(screen.queryByText('View map and itinerary')).not.toBeInTheDocument();
});
