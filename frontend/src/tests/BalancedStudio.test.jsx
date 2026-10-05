import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LabResults from '../pages/AlgorithmLab/LabResults';
import StudioProgress from '../pages/AlgorithmLab/StudioProgress';
import StageRunData from '../pages/AlgorithmLab/StageRunData';

const result = {
  mode: 'live',
  snapshot: { label: 'Fresh', source: 'Providers' },
  stages: [{ name: 'candidates', status: 'complete', detail: 'Measured live discovery' }],
  input_snapshot: { num_stops: 2 },
  explanation: {
    weights: {},
    candidates: [],
    discovery: {
      stop_reason: 'search_budget_exhausted',
      sparse_sections: [3],
      coverage_note: 'Unsearched intervals do not establish continuous coverage.',
      queries: [{ id: 's3-q1', section_id: 3 }],
      unsearched_gaps: [{ largest_unsearched_interval_seconds: 900 }],
    },
    road_checks: [{ detour_raw_seconds: -10, detour_seconds: 0 }],
    solver: {
      objective_direction: 'minimize',
      status: 'FEASIBLE',
      objective_value: 900,
      selected_count: 2,
      requested_stops: 2,
      eligible_count: 5,
      average_match: 0.8,
      best_average_match: 0.9,
      quality_loss: 0.1,
      spacing_deviation_seconds: 600,
      estimated_detour_seconds: 300,
    },
  },
};

it('explains the minimized cost, bounded quality and sparse discovery without historical surplus', async () => {
  render(<LabResults result={result} />);
  await userEvent.click(screen.getByRole('tab', { name: 'Algorithm details' }));
  expect(screen.getByText('Selection cost (seconds)')).toBeInTheDocument();
  expect(screen.getByText(/A valid attraction selection was found/)).toBeInTheDocument();
  expect(screen.getByText(/Sparse sections: 4/)).toBeInTheDocument();
  await userEvent.click(screen.getByText('Constraints and objective formula'));
  expect(
    screen.getByText(/Gaps include origin-to-first and last-to-destination/)
  ).toBeInTheDocument();
  expect(screen.queryByText(/maximize sum/)).not.toBeInTheDocument();
  expect(screen.getByText('10 percentage points')).toBeInTheDocument();
});

it('retains query coverage and measured road exclusions in inspectable stage JSON', async () => {
  render(<StageRunData result={result} />);
  await userEvent.click(screen.getByText('Verified candidates and scores'));
  const data = screen.getByLabelText('Raw data: Verified candidates and scores');
  expect(data).toHaveTextContent('s3-q1');
  expect(data).toHaveTextContent('unsearched_gaps');
  expect(data).toHaveTextContent('detour_raw_seconds');
});

it('shows adaptive upper bounds, query sections and durable actual call counts', () => {
  const view = render(
    <StudioProgress
      events={[
        {
          type: 'progress',
          stage: 'attractions.provider',
          query: 's3-r1',
          section: 3,
          queries: 60,
          adaptive: true,
          state: 'started',
        },
      ]}
    />
  );
  expect(screen.getByRole('status')).toHaveTextContent('of up to 60, section 4');
  view.rerender(
    <StudioProgress
      events={[
        {
          type: 'progress',
          stage: 'providers.activity',
          operation: 'attractions.provider',
          provider: 'nearby',
          active: 4,
          completed: 8,
          peak: 4,
        },
        { type: 'progress', stage: 'attractions.ratings', state: 'started', candidates: 5 },
      ]}
    />
  );
  expect(screen.getByLabelText('Provider call counts')).toHaveTextContent(
    'nearby: 4 active / 8 completed'
  );
});
