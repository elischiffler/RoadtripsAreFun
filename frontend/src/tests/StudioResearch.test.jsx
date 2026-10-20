import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import StudioResearch from '../pages/StudioResearch/StudioResearch';
import {
  Heatmap,
  ResponseCurve,
  RowChart,
  StatusColumns,
  Tradeoff,
  UtilitySpread,
} from '../pages/StudioResearch/ResearchCharts';
import ResearchInfo from '../pages/StudioResearch/ResearchInfo';
import { distribution, paired, sample } from '../pages/StudioResearch/researchData';
import {
  createStudy,
  researchCatalog,
  savedStudies,
  studyRequest,
} from '../services/studioResearch';

vi.mock('../services/studioResearch', () => ({
  createStudy: vi.fn(),
  downloadStudy: vi.fn(),
  researchCatalog: vi.fn(),
  savedStudies: vi.fn(),
  studyRequest: vi.fn(),
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

it('counts the full requested design before starting and updates counts on changes', async () => {
  mount();
  await screen.findByText('6,600');
  expect(screen.getByText(/runs · 300 live trips · 6,300 solver trials/)).toBeInTheDocument();
  expect(createStudy).not.toHaveBeenCalled();
  await userEvent.clear(screen.getByLabelText('Live repeats'));
  await userEvent.type(screen.getByLabelText('Live repeats'), '2');
  expect(screen.getByText('6,360')).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText('CP-SAT only'));
  expect(screen.getByText('60')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Unlock batch runs' })).toBeInTheDocument();
});

it('starts once, remembers the durable study and does not cancel it on unmount', async () => {
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'fixture', expires_at: Date.now() / 1000 + 500 })
  );
  const study = { id: 'fixture-study', key: 'private-fixture' };
  createStudy.mockResolvedValue(study);
  studyRequest.mockImplementation((_study, action) =>
    Promise.resolve(
      action
        ? { state: 'starting' }
        : {
            id: study.id,
            state: 'running',
            counts: { total: 6600, pipeline: 300, solver: 6300 },
            rows: [],
            design: defaults,
            variants,
            dataset_hash: 'abc',
            identity: {},
          }
    )
  );
  const view = mount();
  await userEvent.dblClick(await screen.findByRole('button', { name: 'Start 6,600 runs' }));
  expect(createStudy).toHaveBeenCalledTimes(1);
  expect(studyRequest).toHaveBeenCalledWith(study, 'start', 'post');
  expect(await screen.findByRole('button', { name: 'Pause' })).toBeInTheDocument();
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
  await screen.findByText('complete · 2 / 2');
  await userEvent.click(screen.getByRole('button', { name: 'Full pipeline · 1' }));
  expect(screen.getByText('NOT RUN')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'CP-SAT · 1' }));
  expect(
    screen.getByRole('img', { name: 'Average utility response to quality_loss' })
  ).toBeInTheDocument();
  expect(screen.getByText('100 synthetic candidates · 30 repeats')).toBeInTheDocument();
  expect(screen.getByText('New study').parentElement).not.toHaveAttribute('open');
  expect(screen.queryByText(/Same candidates, persona/)).not.toBeInTheDocument();
  await userEvent.hover(screen.getByRole('button', { name: 'About Parameter response' }));
  expect(screen.getByRole('tooltip')).toHaveTextContent('Trip and stops per day stay fixed');
  await userEvent.unhover(screen.getByRole('button', { name: 'About Parameter response' }));
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Added distance' })).not.toBeInTheDocument();
  expect(screen.getByText('FEASIBLE')).toBeInTheDocument();
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
      <ResponseCurve
        rows={rows}
        variants={variants}
        parameter="quality_loss"
        metric="utility_mean"
      />
      <Tradeoff rows={rows} />
      <UtilitySpread rows={rows} />
    </>
  );
  expect(screen.getByRole('table', { name: 'Average utility · %' })).toHaveTextContent('n=1 / 1');
  expect(screen.getByRole('img', { name: 'Run outcomes by trip type' })).toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'Added driving by trip type' })).toHaveTextContent(
    'minutes'
  );
  expect(
    screen.getByRole('img', { name: 'Average utility response to quality_loss' })
  ).toHaveTextContent('percentage points');
  expect(
    screen.getByRole('img', { name: 'Utility versus added driving scatter plot' })
  ).toHaveTextContent('-1');
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  expect(screen.getByText('40%')).toBeInTheDocument();
  expect(screen.getByText('80%')).toBeInTheDocument();
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
