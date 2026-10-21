import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import StudioResearch from '../pages/StudioResearch/StudioResearch';
import {
  Heatmap,
  RowChart,
  StatusColumns,
  SolverOutcomes,
  Tradeoff,
  UtilitySpread,
} from '../pages/StudioResearch/ResearchCharts';
import ResearchInfo from '../pages/StudioResearch/ResearchInfo';
import { InspectionProvider } from '../pages/StudioResearch/ResearchInspect';
import {
  combineStudies,
  distribution,
  paired,
  sample,
  formatSelectionTime,
  metricValue,
} from '../pages/StudioResearch/researchData';
import {
  loadStudyLibrary,
  researchCatalog,
  savedStudies,
  studyRequest,
  rerunStudy,
  studyVersions,
  savedStudyVersion,
  rememberStudyVersion,
  downloadStudy,
} from '../services/studioResearch';

vi.mock('../services/studioResearch', () => ({
  downloadStudy: vi.fn(),
  loadStudyLibrary: vi.fn(),
  researchCatalog: vi.fn(),
  savedStudies: vi.fn(),
  studyRequest: vi.fn(),
  rerunStudy: vi.fn(),
  studyVersions: vi.fn(),
  savedStudyVersion: vi.fn(),
  rememberStudyVersion: vi.fn(),
}));
const trips = ['short-1d', 'medium-2d', 'long-3d', 'coast-5d', 'tight-2d'].map((id) => ({
  id,
  label: id,
}));
const defaults = {
  trips: trips.map((row) => row.id),
  personas: ['nature', 'entertainment'],
  stops_per_day: [1, 2, 3],
  repeats: 10,
  solver_repeats: 30,
  pipeline: true,
  solver: true,
  departure_date: '2030-11-01',
  quality_loss: [0, 0.05, 0.1, 0.15, 0.2],
  detour_weight: [0.5, 1, 2],
};
const base = {
  id: 1,
  trip: 'medium-2d',
  persona: 'nature',
  stops_per_day: 2,
  target_days: 2,
  repeat: 1,
  variant: 'baseline',
  track: 'solver',
  outcome: 'completed',
  completed: true,
  utility_mean: 0.6,
  utility_min: 0.4,
  utility_median: 0.6,
  utility_max: 0.8,
  utility_values: [0.4, 0.8],
  runtime_seconds: 1,
  solver_seconds: 0.1,
  solver_status: 'FEASIBLE',
  extra_seconds: -60,
};
const variants = [
  { id: 'baseline', parameter: 'baseline' },
  { id: 'loss-0', parameter: 'quality_loss', value: 0 },
  { id: 'loss-02', parameter: 'quality_loss', value: 0.2 },
];

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  researchCatalog.mockResolvedValue({ trips, personas: defaults.personas, defaults });
  savedStudies.mockReturnValue([]);
  savedStudyVersion.mockReturnValue('current');
  studyVersions.mockResolvedValue({ currentLabel: '', previous: null });
});
afterEach(() => {
  vi.useRealTimers();
  sessionStorage.clear();
});
const mount = () =>
  render(
    <MemoryRouter>
      <StudioResearch />
    </MemoryRouter>
  );

it('normalizes solver outcomes and connects segment hover and focus to legend counts', async () => {
  const user = userEvent.setup();
  render(<SolverOutcomes counts={{ OPTIMAL: 3, FEASIBLE: 1, INFEASIBLE: 0, UNKNOWN: 0 }} />);
  const bar = screen.getByRole('group', { name: 'CP-SAT outcome percentages' });
  const optimal = within(bar).getByRole('img', { name: 'Optimal: 75%, 3 runs' });
  expect(optimal).toHaveStyle({ width: '75%' });
  expect(within(bar).getByRole('img', { name: 'Feasible: 25%, 1 run' })).toHaveStyle({
    width: '25%',
  });
  expect(within(bar).getAllByRole('img')).toHaveLength(2);
  const legend = screen.getByRole('list', { name: 'CP-SAT outcome counts' });
  const optimalLegend = within(legend).getByText('Optimal').closest('li');
  expect(within(optimalLegend).getByText('3')).toBeInTheDocument();
  expect(within(legend).getByText('Infeasible').closest('li')).toHaveTextContent('0');
  await user.hover(optimal);
  expect(optimalLegend).toHaveClass('is-highlighted');
  expect(within(legend).getByText('Feasible').closest('li')).not.toHaveClass('is-highlighted');
  await user.unhover(optimal);
  expect(optimalLegend).not.toHaveClass('is-highlighted');
  await user.tab();
  expect(optimalLegend).toHaveClass('is-highlighted');
});

it('offers Studio access in a browser without saved study keys', async () => {
  mount();
  expect(await screen.findByText('Enter Studio password')).toBeInTheDocument();
  expect(screen.queryByText('New study')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Studio password')).not.toBeInTheDocument();
  expect(studyRequest).not.toHaveBeenCalled();
});

it('combines saved results without selecting a study or cancelling work on unmount', async () => {
  const studies = [
    { id: 'current', key: 'first-key' },
    { id: 'pilot', key: 'second-key' },
  ];
  savedStudies.mockReturnValue(studies);
  studyRequest.mockImplementation((study) =>
    Promise.resolve({
      state: study.id === 'current' ? 'running' : 'complete',
      counts: { total: 1, pipeline: 0, solver: 1 },
      design: defaults,
      variants,
      dataset_hash: 'same-data',
      rows: [{ ...base, utility_mean: study.id === 'current' ? 0.6 : 0.8 }],
    })
  );
  const view = mount();
  expect(await screen.findByText('running · 2 / 2')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Stop selection · 2' })).toBeInTheDocument();
  expect(screen.getByRole('table')).toHaveTextContent('2 runs measured');
  expect(screen.queryByLabelText('Study')).not.toBeInTheDocument();
  expect(screen.queryByText('New study')).not.toBeInTheDocument();
  expect(studyRequest.mock.calls.every(([, action]) => !action)).toBe(true);
  view.unmount();
  expect(studyRequest.mock.calls.some(([, action]) => action === 'pause')).toBe(false);
});

it('restores a study without Studio login, separates tracks and keeps failures visible', async () => {
  const study = { id: 'saved', key: 'private-fixture' };
  savedStudies.mockReturnValue([study]);
  studyRequest.mockResolvedValue({
    state: 'complete',
    counts: { total: 2, pipeline: 1, solver: 1 },
    design: defaults,
    variants,
    dataset_hash: 'abc',
    identity: { revision: 'frozen', metric_version: 'fixture' },
    rows: [
      {
        ...base,
        track: 'pipeline',
        id: 10,
        outcome: 'failed',
        completed: false,
        solver_status: 'NOT_RUN',
      },
      base,
    ],
  });
  mount();
  await screen.findByText('Finished · 2 / 2');
  expect(screen.getByText('100% of finished runs')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Full trip planning · 1' }));
  expect(screen.getByText('Not run')).toBeInTheDocument();
  expect(screen.getByText('0% of finished runs')).toBeInTheDocument();
  expect(screen.getByText('1 failed · 0 partial · 0 interrupted')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Stop selection · 1' }));
  expect(screen.queryByText('Settings comparison')).not.toBeInTheDocument();
  expect(screen.getByText('100 simulated attractions')).toBeInTheDocument();
  expect(screen.queryByText('New study')).not.toBeInTheDocument();
  expect(screen.queryByText(/Same candidates, persona/)).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Added distance' })).not.toBeInTheDocument();
  expect(screen.getByText('Feasible')).toBeInTheDocument();
});

it('does not confuse zeroes, missing measurements, failed trials or unmatched pairs', () => {
  expect(distribution([0, 1, null, NaN])).toMatchObject({
    n: 2,
    mean: 0.5,
    median: 0.5,
    min: 0,
    max: 1,
  });
  expect(distribution([])).toMatchObject({ n: 0, mean: null, median: null });
  const rows = [
    base,
    { ...base, variant: 'tuned', utility_mean: 0.5 },
    { ...base, persona: 'entertainment', variant: 'tuned', utility_mean: 1 },
    { ...base, repeat: 2, variant: 'tuned', completed: false, utility_mean: 1 },
  ];
  expect(paired(rows, 'tuned', 'utility_mean')).toMatchObject({ n: 1, mean: -10 });
  expect(sample([{ ...base, completed: false, utility_mean: 1 }], 'utility_mean').n).toBe(0);
  expect(
    sample([{ ...base, completed: false, runtime_seconds: 0 }], 'runtime_seconds')
  ).toMatchObject({ n: 1, mean: 0 });
});

it('renders charts with labeled units, measured sample sizes and negative driving deltas', () => {
  const rows = [
    base,
    {
      ...base,
      id: 2,
      persona: 'entertainment',
      variant: 'loss-0',
      utility_mean: 0.9,
      extra_seconds: 120,
    },
  ];
  const { container } = render(
    <>
      <Heatmap rows={rows} trips={trips} metric="utility_mean" />
      <StatusColumns rows={rows} trips={trips} />
      <RowChart rows={rows} trips={trips} metric="extra_seconds" />
      <Tradeoff rows={rows} />
      <UtilitySpread rows={rows} />
    </>
  );
  expect(screen.getByRole('table', { name: 'Mean utility score · %' })).toHaveTextContent(
    '1 run measured'
  );
  expect(screen.getByRole('group', { name: 'Run outcomes by trip type' })).toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Added driving by trip type' })).toHaveTextContent(
    'minutes'
  );
  expect(
    screen.getByRole('group', { name: 'Mean utility score versus added driving scatter plot' })
  ).toHaveTextContent('-1');
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  expect(
    within(container.querySelector('.research-stat-row')).getByText('40%')
  ).toBeInTheDocument();
  expect(
    within(container.querySelector('.research-stat-row')).getByText('80%')
  ).toBeInTheDocument();
});

it('opens chart help on hover, focus or tap and dismisses it with Escape or an outside tap', async () => {
  render(
    <>
      <ResearchInfo label="Repeat variation">The box contains the middle 50% of runs.</ResearchInfo>
      <button>Outside</button>
    </>
  );
  const info = screen.getByRole('button', { name: 'About Repeat variation' });
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  await userEvent.hover(info);
  expect(screen.getByRole('tooltip')).toHaveTextContent('middle 50%');
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  await userEvent.unhover(info);
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  await userEvent.tab();
  expect(info).toHaveFocus();
  expect(info).toHaveAccessibleDescription('The box contains the middle 50% of runs.');
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  await userEvent.click(info);
  expect(screen.getByRole('tooltip')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Outside' }));
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
});

it('centers heatmap colors on equally weighted populated cells and keeps unknowns blank', () => {
  const groups = trips.slice(0, 3);
  const rows = [
    { ...base, trip: groups[0].id, stops_per_day: 1, utility_mean: 0.6 },
    { ...base, trip: groups[1].id, stops_per_day: 1, utility_mean: 0.7 },
    { ...base, trip: groups[2].id, stops_per_day: 1, utility_mean: 0.8 },
    { ...base, trip: groups[2].id, stops_per_day: 1, utility_mean: 0.8, repeat: 2 },
    { ...base, trip: groups[0].id, stops_per_day: 2, utility_mean: 1, completed: false },
  ];
  const view = render(<Heatmap rows={rows} trips={groups} metric="utility_mean" />);
  const table = screen.getByRole('table');
  const scores = within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[0]);
  expect(screen.getByText('Mean 70%')).toBeInTheDocument();
  expect(scores[0]).toHaveStyle({ background: 'rgb(232, 199, 168)' });
  expect(scores[1]).toHaveStyle({ background: 'rgb(247, 244, 237)' });
  expect(scores[2]).toHaveStyle({ background: 'rgb(179, 209, 200)' });
  const unknown = within(table).getAllByRole('row')[1];
  expect(within(unknown).getAllByRole('cell')[1]).toHaveTextContent('—');
  expect(within(unknown).getAllByRole('cell')[1].style.background).toBe('');
  view.rerender(<Heatmap rows={[rows[1]]} trips={groups} metric="utility_mean" />);
  expect(screen.getByText('Mean 70% · No variation')).toBeInTheDocument();
  expect(view.container.querySelector('.research-heatmap-gradient')).toBeNull();
  view.rerender(<Heatmap rows={[]} trips={groups} metric="utility_mean" />);
  expect(screen.queryByLabelText('Heatmap color scale')).not.toBeInTheDocument();
  expect(view.container.innerHTML).not.toMatch(/NaN|Infinity/);
});

it('keeps source identities and parameter pairs separate when merging matching case IDs', () => {
  const snapshot = (id, rows) => ({
    id,
    state: 'complete',
    counts: { total: rows.length, pipeline: 0, solver: rows.length },
    design: defaults,
    variants,
    dataset_hash: 'fixed-data',
    rows,
  });
  const data = combineStudies([
    snapshot('main', [base, { ...base, id: 2, variant: 'tuned', utility_mean: 0.5 }]),
    snapshot('pilot', [{ ...base, variant: 'tuned', utility_mean: 0.9 }]),
  ]);
  expect(data.counts).toEqual({ total: 3, pipeline: 0, solver: 3 });
  expect(new Set(data.rows.map((row) => row.id)).size).toBe(3);
  expect(paired(data.rows, 'tuned', 'utility_mean')).toMatchObject({ n: 1, mean: -10 });
});

it('shows measured run counts and observed ranges without treating a failed run as a zero score', () => {
  const rows = [
    { ...base, utility_mean: 0.5 },
    { ...base, id: 2, utility_mean: 0.9 },
    { ...base, id: 3, completed: false, outcome: 'failed', utility_mean: 0 },
  ];
  const { container } = render(<Heatmap rows={rows} trips={trips} metric="utility_mean" />);
  const row = within(screen.getByRole('table')).getAllByRole('row')[2];
  const cell = within(row).getAllByRole('cell')[1];
  expect(cell).toHaveTextContent('70');
  expect(cell).toHaveTextContent('2 of 3 runs measured');
  expect(cell).toHaveTextContent('Range 50–90%');
  expect(container.textContent).not.toMatch(/\bn=|\bSD=/);
});

it('plots attraction score frequencies with exact bin boundaries, excluding failed and invalid scores', () => {
  const rows = [
    { ...base, utility_values: [0, 0.049, 0.05] },
    { ...base, id: 2, utility_values: [0.999, 1, null, NaN, -0.1, 1.1] },
    { ...base, id: 3, completed: false, utility_values: [0.5] },
  ];
  const view = render(<UtilitySpread rows={rows} />);
  const chart = screen.getByRole('group', { name: 'Distribution of attraction utility scores' });
  expect(screen.getByText('5 utility scores · 2 runs')).toBeInTheDocument();
  expect(chart).toHaveAccessibleDescription(
    expect.stringContaining('0% to below 5%: 2 utility scores (40%)')
  );
  expect(chart).toHaveAccessibleDescription(
    expect.stringContaining('5% to below 10%: 1 utility score (20%)')
  );
  expect(chart).toHaveAccessibleDescription(
    expect.stringContaining('95% to 100%: 2 utility scores (40%)')
  );
  expect(chart).toHaveAccessibleDescription(
    expect.stringContaining('50% to below 55%: 0 utility scores (0%)')
  );
  expect(view.container.innerHTML).not.toMatch(/NaN|Infinity/);
  view.rerender(<UtilitySpread rows={[]} />);
  expect(screen.getByText('No utility scores yet.')).toBeInTheDocument();
  expect(
    screen.queryByRole('group', { name: 'Distribution of attraction utility scores' })
  ).not.toBeInTheDocument();
});

it('reveals one contextual insight at a time and supports arrow-key chart navigation', async () => {
  const rows = [base, { ...base, id: 2, persona: 'entertainment', utility_mean: 0.8 }];
  const view = render(
    <InspectionProvider>
      <Heatmap rows={rows} trips={trips} metric="utility_mean" />
    </InspectionProvider>
  );
  const cells = within(screen.getByRole('table'))
    .getAllByRole('cell')
    .filter((cell) => cell.hasAttribute('data-inspection-target'));
  expect(cells[0]).toHaveAttribute('tabindex', '0');
  expect(cells[1]).toHaveAttribute('tabindex', '-1');
  expect(cells[0]).not.toHaveAttribute('title');
  await userEvent.hover(cells[0]);
  expect(await screen.findByRole('tooltip')).toHaveTextContent('10 points below');
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('60%');
  await userEvent.click(cells[0]);
  await userEvent.keyboard('{ArrowRight}');
  expect(cells[1]).toHaveFocus();
  expect(cells[1]).toHaveAttribute('tabindex', '0');
  expect(cells[0]).toHaveAttribute('tabindex', '-1');
  expect(screen.getAllByRole('tooltip')).toHaveLength(1);
  expect(screen.getByRole('tooltip')).toHaveTextContent('10 points above');
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  view.unmount();
});

it('inspects histogram shares without echoing visible bar counts and clears the insight on scroll', async () => {
  render(
    <InspectionProvider>
      <UtilitySpread rows={[{ ...base, utility_values: [0.6, 0.6, 0.8] }]} />
    </InspectionProvider>
  );
  const chart = screen.getByRole('group', { name: 'Distribution of attraction utility scores' });
  const bar = within(chart).getByRole('button', { name: /60% to below 65%/ });
  await userEvent.click(bar);
  expect(screen.getByRole('tooltip')).toHaveTextContent('60–65% · 66.7% of utility scores');
  expect(screen.getByRole('tooltip')).not.toHaveTextContent('2 utility scores');
  act(() => window.dispatchEvent(new Event('scroll')));
  await vi.waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument());
});

it('labels the trip measure and prints distinct mean and median values without a hover', () => {
  render(
    <InspectionProvider>
      <RowChart
        rows={[
          { ...base, utility_mean: 0.4 },
          { ...base, id: 2, utility_mean: 0.5 },
          { ...base, id: 3, utility_mean: 0.9 },
        ]}
        trips={trips}
        metric="utility_mean"
      />
    </InspectionProvider>
  );
  expect(screen.getByText('Utility score by trip')).toBeInTheDocument();
  const chart = screen.getByRole('group', { name: 'Mean utility score by trip type' });
  const row = within(chart).getByText('3 runs measured').closest('.research-trip-row');
  expect(row).toHaveTextContent('Mean 60%');
  expect(row).toHaveTextContent('Median 50%');
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  expect(within(chart).getByRole('button', { name: /measured range/ })).toBeInTheDocument();
  expect(chart).toHaveTextContent('35%');
  expect(chart).toHaveTextContent('95%');
  expect(screen.queryByText('Consistency across runs')).not.toBeInTheDocument();
});

it('reruns the largest saved matrix without pooling historical results or starting live trips', async () => {
  const previous = { id: 'previous', key: 'previous-key' };
  const replacement = { id: 'replacement', key: 'replacement-key' };
  savedStudies.mockReturnValue([previous]);
  const snapshot = {
    state: 'paused',
    counts: { total: 2, pipeline: 1, solver: 1 },
    design: defaults,
    variants: [{ ...variants[0], config: { time_limit_seconds: 5 } }],
    dataset_hash: 'fixed',
    rows: [base],
  };
  studyRequest.mockImplementation((study) =>
    Promise.resolve(
      study.id === 'previous'
        ? snapshot
        : {
            ...snapshot,
            state: 'running',
            counts: { total: 1, pipeline: 0, solver: 1 },
            variants: [{ ...variants[0], config: { time_limit_seconds: 15 } }],
            rows: [],
          }
    )
  );
  rerunStudy.mockResolvedValue(replacement);
  mount();
  await screen.findByText('5 s solve limit');
  await userEvent.click(screen.getByRole('button', { name: 'Rerun stop selection' }));
  expect(rerunStudy).toHaveBeenCalledWith(previous, [previous]);
  await screen.findByText('15 s solve limit');
  expect(studyRequest).toHaveBeenCalledWith(replacement, 'start', 'post');
  expect(studyVersions).toHaveBeenCalledWith([replacement], expect.anything(), [previous]);
  expect(screen.queryByRole('table')).toHaveTextContent('—');
  expect(screen.queryByRole('button', { name: /Full trip planning/ })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Rerun stop selection' })).toBeDisabled();
});

it('switches versions without mixing results, mutating batches or changing the current worker', async () => {
  const current = { id: 'current', key: 'current-key' };
  const previous = { id: 'previous', key: 'previous-key' };
  savedStudies.mockReturnValue([current]);
  studyVersions.mockResolvedValue({
    currentLabel: '15',
    previous: { study: previous, label: '5' },
  });
  studyRequest.mockImplementation((study) =>
    Promise.resolve({
      id: study.id,
      state: study.id === 'current' ? 'running' : 'paused',
      counts: { total: 1, solver: 1, pipeline: 0 },
      design: defaults,
      dataset_hash: 'same',
      variants: [
        { ...variants[0], config: { time_limit_seconds: study.id === 'current' ? 15 : 5 } },
      ],
      rows: [{ ...base, utility_mean: study.id === 'current' ? 0.8 : 0.6 }],
    })
  );
  mount();
  const versions = await screen.findByRole('navigation', { name: 'Study version' });
  expect(within(versions).getByRole('button', { name: '15 s' })).toHaveAttribute(
    'aria-pressed',
    'true'
  );
  await screen.findByRole('table');
  expect(screen.getByRole('table')).toHaveTextContent('80');
  await userEvent.click(within(versions).getByRole('button', { name: '5 s' }));
  await screen.findByText('5 s solve limit');
  expect(screen.getByRole('table')).toHaveTextContent('60');
  expect(screen.getByText('Archived · 1 / 1')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Resume' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Pause' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Rerun stop selection' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
  expect(downloadStudy).toHaveBeenCalledWith([previous], 'csv');
  await userEvent.click(within(versions).getByRole('button', { name: '15 s' }));
  await screen.findByText('15 s solve limit');
  expect(screen.getByRole('table')).toHaveTextContent('80');
  expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  expect(studyRequest.mock.calls.every(([, action]) => !action)).toBe(true);
  expect(rememberStudyVersion).toHaveBeenCalledWith('previous');
  expect(rememberStudyVersion).toHaveBeenLastCalledWith('current');
});

it('formats selection milliseconds without changing stored seconds or losing zero and missing values', () => {
  expect(formatSelectionTime(metricValue({ solver_seconds: 0.125 }, 'solver_seconds'))).toBe(
    '125 ms'
  );
  expect(formatSelectionTime(metricValue({ solver_seconds: 2.5 }, 'solver_seconds'))).toBe('2.5 s');
  expect(formatSelectionTime(0)).toBe('0 ms');
  expect(formatSelectionTime(0.001)).toBe('<0.01 ms');
  expect(formatSelectionTime(999)).toBe('999 ms');
  expect(formatSelectionTime(1000)).toBe('1 s');
  expect(formatSelectionTime(60000)).toBe('1 min');
  expect(formatSelectionTime(3600000)).toBe('1 h');
  expect(formatSelectionTime(-1500)).toBe('-1.5 s');
  expect(formatSelectionTime(null)).toBe('—');
  expect(formatSelectionTime(NaN)).toBe('—');
});

it('uses adaptive units in selection-time cells, ranges and chart values', () => {
  const rows = [
    { ...base, solver_seconds: 2.5 },
    { ...base, id: 2, solver_seconds: 0.5, repeat: 2 },
    { ...base, id: 3, solver_seconds: 1, variant: 'loss-0' },
  ];
  render(
    <InspectionProvider>
      <Heatmap
        rows={rows.filter((row) => row.variant === 'baseline')}
        trips={trips}
        metric="solver_seconds"
      />
      <RowChart
        rows={rows.filter((row) => row.variant === 'baseline')}
        trips={trips}
        metric="solver_seconds"
      />
    </InspectionProvider>
  );
  const table = screen.getByRole('table', { name: 'Selection time' });
  expect(table).toHaveTextContent('1.5 s');
  expect(table).toHaveTextContent('Range 500 ms–2.5 s');
  const chart = screen.getByRole('group', { name: 'Selection time by trip type' });
  expect(chart).toHaveTextContent('Mean 1.5 s');
  expect(chart).toHaveTextContent('Median 1.5 s');
  expect(table).not.toHaveTextContent('1,500');
  expect(rows[0].solver_seconds).toBe(2.5);
});

it('loads database studies in a fresh browser and keeps shared results read-only', async () => {
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'fixture-session', expires_at: Date.now() / 1000 + 3600 })
  );
  loadStudyLibrary.mockResolvedValue({
    current: [{ id: 'database-study', database: true }],
    archived: [],
  });
  studyRequest.mockResolvedValue({
    state: 'running',
    counts: { total: 7, solver: 7, pipeline: 0 },
    design: defaults,
    variants,
    dataset_hash: 'same-data',
    rows: [
      base,
      { ...base, id: 2, solver_status: 'OPTIMAL' },
      { ...base, id: 3, completed: false, outcome: 'failed', solver_status: 'UNKNOWN' },
    ],
  });
  mount();
  expect(await screen.findByText('running · 3 / 7')).toBeInTheDocument();
  expect(loadStudyLibrary).toHaveBeenCalled();
  expect(screen.getByText('CP-SAT outcomes')).toBeInTheDocument();
  expect(screen.getByText('Optimal')).toBeInTheDocument();
  expect(screen.getByText('Feasible')).toBeInTheDocument();
  expect(screen.getByText('Unknown')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Pause' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Rerun stop selection' })).not.toBeInTheDocument();
  act(() => {
    sessionStorage.removeItem('studioSession');
    window.dispatchEvent(new Event('studio-access-changed'));
  });
  expect(await screen.findByText('Enter Studio password')).toBeInTheDocument();
});
