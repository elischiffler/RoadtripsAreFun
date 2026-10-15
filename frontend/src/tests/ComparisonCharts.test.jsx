import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ComparisonCharts from '../pages/AlgorithmLab/ComparisonCharts';
import { comparisonGroups } from '../pages/AlgorithmLab/comparisonGroups';

const row = (id, status = 'completed', mean = 0.8) => ({
  id,
  preset_id: 'unit-contract-only',
  mode: 'live',
  status,
  metrics: {
    cohort_key: 'unit-inputs',
    candidate_hash: 'unit-candidates',
    revision: 'unit-revision',
    metric_version: 'unit-metrics',
    evidence_layer: 'live_pipeline',
    solver_status: status === 'failed' ? 'UNKNOWN' : 'OPTIMAL',
    candidate_snapshot: [{ source_generation: 'unit-generation', source_release: 'unit-release' }],
    trip_evaluation: {
      completed: status === 'completed',
      stop_fulfillment: { ratio: 1 },
      schedule_compliance: { violation_count: 0 },
      utility: { delivered: { mean } },
      driving_gaps: { maximum_stretch_seconds: 3600 },
      hotel_costs: {
        above_target_total_usd: 20,
        budget_utilization: 1.2,
        over_target_fraction: 0.5,
      },
    },
  },
});

describe('page comparison charts', () => {
  it('keeps failed and synthetic outputs out of distributions and retains raw statuses', () => {
    const synthetic = row('synthetic');
    synthetic.metrics.evidence_layer = 'synthetic_unit_only';
    render(<ComparisonCharts rows={[row('one'), row('failed', 'failed', 0.99), synthetic]} />);
    expect(screen.getByText(/1 successful fulfilled \/ 2 recorded/)).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: 'Delivered attraction utility, 1 assessed outputs' })
    ).toBeInTheDocument();
    expect(screen.getByText(/UNKNOWN: 1.00 runs/)).toBeInTheDocument();
    expect(screen.getByText(/Catalog generation: unit-generation/)).toBeInTheDocument();
    expect(screen.queryByText('99.000')).not.toBeInTheDocument();
  });
  it('separates changed candidate pools and versions', () => {
    const changed = row('two');
    changed.metrics.candidate_hash = 'different-pool';
    const version = row('three');
    version.metrics.metric_version = 'different-version';
    expect(comparisonGroups([row('one'), changed, version])).toHaveLength(3);
  });
  it('shows a clear empty state for old or unassessed history', () => {
    render(<ComparisonCharts rows={[{ status: 'completed', mode: 'replay' }]} />);
    expect(
      screen.getByText('No comparable measured live records on this page.')
    ).toBeInTheDocument();
  });
  it('renders quartiles only with enough calculated observations', () => {
    render(
      <ComparisonCharts
        rows={[
          row('one', 'completed', 0.6),
          row('two', 'completed', 0.7),
          row('three', 'completed', 0.8),
          row('four', 'completed', 0.9),
        ]}
      />
    );
    expect(screen.getAllByText(/1.5 × IQR whiskers/)).toHaveLength(2);
  });
});
