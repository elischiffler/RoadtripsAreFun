import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RunHistory from '../pages/AlgorithmLab/RunHistory';
import { getLabRuns } from '../services/algorithmLab';
import TripEvaluation from '../pages/AlgorithmLab/TripEvaluation';

const metrics = {
  trip_evaluation: {
    driving: {
      extra_distance_meters: 1609.344,
      extra_distance_percent: 10,
      extra_duration_seconds: 3600,
      extra_duration_percent: 20,
    },
    stop_fulfillment: { delivered: 1, requested: 2, solver_selected: 1, ratio: 0.5 },
    schedule: {
      itinerary_days: null,
      overnights: 1,
      final_arrival: '2026-10-07T19:00:00-07:00',
      final_timezone: 'America/Los_Angeles',
      elapsed_trip_seconds: 86400,
      assessment_reason: 'schedule_incomplete',
    },
    schedule_compliance: { violation_count: 0, assessed_stops: 3, min_deadline_slack_seconds: 600 },
    hotel_costs: {
      quoted_total_usd: 200,
      room_night_count: 2,
      max_room_night_usd: 120,
      over_target_room_nights: 1,
      above_target_total_usd: 20,
    },
    first_failed_stage: 'itinerary',
    error_code: 'provider_or_planning_failure',
    warnings: ['Confirm check-in'],
  },
};

describe('trip evaluation', () => {
  it('keeps historical and unfinished records readable', () => {
    render(<TripEvaluation metrics={{ metric_version: 'selection-surplus-v1' }} />);
    expect(screen.getByText(/older or unfinished run/)).toBeInTheDocument();
  });
  it('renders partial outcomes with units, warnings and missing-evidence reasons', () => {
    render(<TripEvaluation metrics={metrics} />);
    expect(screen.getByText(/1 miles/)).toBeInTheDocument();
    expect(screen.getByText(/50%/)).toBeInTheDocument();
    expect(screen.getByText(/schedule incomplete/)).toBeInTheDocument();
    expect(screen.getByText(/itinerary provider_or_planning_failure/)).toBeInTheDocument();
    expect(screen.getByText('Confirm check-in')).toBeInTheDocument();
    expect(screen.getByText(/exclude fuel, food and admission/)).toBeInTheDocument();
  });
});

vi.mock('../services/algorithmLab', () => ({
  getLabRuns: vi.fn(),
  labError: (error) => error.message,
}));

it('shows page-scoped statistics beside both old and new history records', async () => {
  const old = {
    metric_version: 'selection-surplus-v1',
    cohort_key: 'old',
    latency_ms: { total: 10 },
    external_calls: {},
    objective_score: 1,
  };
  const current = { ...old, ...metrics, metric_version: 'selection-surplus-v2', cohort_key: 'new' };
  getLabRuns.mockResolvedValue({
    runs: [
      {
        id: 'old',
        preset_id: 'coast',
        started_at: '2026-10-05T12:00:00Z',
        status: 'completed',
        mode: 'live',
        metrics: old,
      },
      {
        id: 'new',
        preset_id: 'coast',
        started_at: '2026-10-05T13:00:00Z',
        status: 'failed',
        mode: 'live',
        metrics: current,
      },
    ],
    groups: [
      {
        cohort_key: 'new',
        metric_version: 'selection-surplus-v2',
        runs: 1,
        trip_evaluation: {
          extra_distance_meters: { mean: 10, stddev: 0, min: 10, max: 10, count: 1 },
        },
      },
    ],
    page_summary: {
      completed: 1,
      failed: 1,
      unfinished: 0,
      completion_rate: 0.5,
      completion_assessed: 2,
    },
    next_offset: null,
  });
  render(<RunHistory revision={0} />);
  expect(await screen.findByText(/Current page: 1 completed, 1 failed/)).toBeInTheDocument();
  expect(screen.getByText(/older or unfinished run/)).toBeInTheDocument();
  expect(screen.getByText(/extra distance meters: 10.00/)).toHaveTextContent('1 assessed');
});
