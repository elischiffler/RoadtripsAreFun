import { expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StageRunData from '../pages/AlgorithmLab/StageRunData';

function result() {
  return {
    stages: [
      'inputs',
      'endpoints',
      'initial_route',
      'candidates',
      'selection',
      'scheduling',
      'reroute',
      'itinerary',
    ].map((name) => ({ name, status: 'complete', detail: `Recorded ${name}` })),
    input_snapshot: {
      num_stops: 2,
      traveler_count: 3,
      budget: 123.45,
      start_date: '2026-10-06T09:00:00-07:00',
      start: {
        label: 'San Francisco',
        coordinates: [37.7, -122.4],
        timezone: 'America/Los_Angeles',
      },
      destination: { label: 'Monterey', coordinates: [36.6, -121.9] },
      hotel_rooms: [{ adults: 3, child_ages: [] }],
      scheduling_policy: { morning_restart: '09:00' },
    },
    direct_route: { distance: 160934.4, duration: 7200 },
    explanation: {
      weights: { nature: 0.75, history: 0.25 },
      query_points: [[37, -122]],
      candidates: [
        {
          name: 'A <forest> walk',
          provider_id: 'place-one',
          selected: true,
          utility: 0.7123456789,
          contributions: [{ attribute: 'nature', contribution: 0.6 }],
        },
        { name: 'Market', selected: false, reason: 'below_utility_threshold' },
      ],
      solver: { status: 'OPTIMAL', eligible_count: 1, selected_count: 1, objective_value: 123456 },
    },
    route: {
      distance: 177027.84,
      duration: 9000,
      cost: 99.5,
      geometry: {
        coordinates: [
          [-122.4, 37.7],
          [-121.9, 36.6],
        ],
      },
      stops: [
        { name: 'A <forest> walk', type: 'stop' },
        { name: 'Hotel', type: 'hotel', price: 99.5 },
      ],
    },
    itinerary: [{ date: '2026-10-06', stops: [] }],
  };
}
async function open(label) {
  await userEvent.click(screen.getByText(label));
  return screen.findByLabelText(`Raw data: ${label}`);
}

it('shows useful summaries and lazily displays precise candidate scores and backend provenance', async () => {
  const data = result();
  render(<StageRunData result={data} />);
  expect(screen.getByText('Run data by stage')).toBeInTheDocument();
  expect(screen.getByText('2 retained candidates · 1 route sample')).toBeInTheDocument();
  expect(screen.getByText('OPTIMAL · 1 selected / 1 eligible')).toBeInTheDocument();
  expect(
    screen.queryByLabelText('Raw data: Verified candidates and scores')
  ).not.toBeInTheDocument();
  const raw = await open('Verified candidates and scores');
  expect(JSON.parse(raw.textContent)).toEqual({
    effective_weights: data.explanation.weights,
    query_points: data.explanation.query_points,
    candidates: data.explanation.candidates,
  });
  expect(raw).toHaveTextContent('0.7123456789');
  expect(raw.querySelector('forest')).toBeNull();
  await userEvent.click(screen.getByText('Verified candidates and scores'));
  await waitFor(() =>
    expect(
      screen.queryByLabelText('Raw data: Verified candidates and scores')
    ).not.toBeInTheDocument()
  );
});

it('exposes actual validated inputs, geocoded endpoints, and direct route units', async () => {
  const data = result();
  render(<StageRunData result={data} />);
  expect(screen.getByText('100 miles · 2 driving hours')).toBeInTheDocument();
  expect(JSON.parse((await open('Validated trip inputs')).textContent)).toEqual(
    data.input_snapshot
  );
  expect(JSON.parse((await open('Resolved cities and timezones')).textContent).start).toEqual(
    data.input_snapshot.start
  );
  expect(JSON.parse((await open('Starting road route')).textContent)).toEqual(data.direct_route);
  expect(
    screen.getByText('Only distance and duration were retained for the starting route.')
  ).toBeInTheDocument();
});

it('preserves solver output, selected candidates, final stops and itinerary without inventing intermediate data', async () => {
  const data = result();
  render(<StageRunData result={data} />);
  const selection = JSON.parse((await open('CP-SAT selection')).textContent);
  expect(selection.solver).toEqual(data.explanation.solver);
  expect(selection.selected_candidates).toEqual([data.explanation.candidates[0]]);
  expect(JSON.parse((await open('Scheduled visits and hotels')).textContent).stops).toEqual(
    data.route.stops
  );
  expect(screen.getByText(/an intermediate scheduler response was not saved/)).toBeInTheDocument();
  expect(JSON.parse((await open('Final road route')).textContent)).toEqual(data.route);
  expect(JSON.parse((await open('Dated itinerary')).textContent)).toEqual(data.itinerary);
});

it('shows retained failure diagnostics and does not turn missing output into fake zero counts', async () => {
  const data = {
    stages: [
      { name: 'endpoints', status: 'failed', detail: 'City provider unavailable' },
      { name: 'itinerary', status: 'not_run', detail: 'Not reached' },
    ],
    error: { code: '503', message: 'City provider unavailable' },
    input_snapshot: {},
  };
  render(<StageRunData result={data} />);
  expect(screen.getAllByText('No stage data retained')).toHaveLength(2);
  expect(JSON.parse((await open('Resolved cities and timezones')).textContent)).toEqual({
    error: data.error,
  });
  await userEvent.click(screen.getByText('Dated itinerary'));
  expect(
    await screen.findByText('No input or output data was retained for this stage.')
  ).toBeInTheDocument();
  expect(screen.queryByText('0 itinerary days')).not.toBeInTheDocument();
});
