import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import TripStats from '../pages/AlgorithmLab/TripStats';

import result from './fixtures/studioStats';

const figure = (label) => screen.getByText(label, { selector: 'dt' }).nextElementSibling;

it('keeps chosen and delivered counts separate and shows match estimates as percentages', () => {
  render(<TripStats result={result} />);
  expect(figure('Attractions')).toHaveTextContent('2 / 4');
  expect(figure('Chosen')).toHaveTextContent('3');
  expect(figure('On trip')).toHaveTextContent('2');
  expect(figure('Match estimate')).toHaveTextContent('80%');
  const places = screen.getByRole('region', { name: 'Place match estimates' });
  expect(within(places).getByText('Gallery').parentElement).toHaveTextContent('Chosen');
  expect(within(places).getByText('Museum').parentElement).toHaveTextContent('On trip');
  expect(screen.getByRole('group', { name: 'Museum match' })).toHaveTextContent('90%');
  expect(figure('Nightly target used')).toHaveTextContent('68.1%');
});

it('compares actual road values in common units and keeps planning durations independent', () => {
  render(<TripStats result={result} />);
  const driving = screen.getByRole('group', { name: 'Driving time' });
  expect(driving).toHaveTextContent('Direct2 hrWith stops3 hr');
  expect(screen.getByRole('group', { name: 'Driving distance' })).toHaveTextContent('100 mi');
  expect(figure('Extra driving')).toHaveTextContent('1 hr');
  expect(figure('Planning time')).toHaveTextContent('2 min 30 sec');
  expect(figure('Choosing time')).toHaveTextContent('<0.1 sec');
  expect(figure('Catalog searches')).toHaveTextContent('12');
  expect(screen.getByRole('group', { name: 'Planning stage times' })).toHaveTextContent(
    '1 min 40 sec'
  );
  expect(figure('Arrival')).toHaveTextContent('Oct 22, 2026');
  expect(figure('Arrival')).toHaveTextContent('America/Boise');
});

it('shows unknown measurements as dashes while retaining measured zeros', () => {
  render(
    <TripStats
      result={{
        run_record: {
          metrics: {
            trip_evaluation: {
              hotel_costs: { quoted_total_usd: 0 },
              schedule_compliance: { violation_count: 0 },
            },
          },
        },
      }}
    />
  );
  expect(figure('Attractions')).toHaveTextContent('— / —');
  expect(figure('Match estimate')).toHaveTextContent('—');
  expect(figure('Late stops')).toHaveTextContent('0');
  expect(figure('Total')).toHaveTextContent('$0');
  expect(figure('Room nights')).toHaveTextContent('—');
  expect(figure('Considered')).toHaveTextContent('—');
});

it('keeps negative road differences signed and never converts unknown values to zero', () => {
  const data = structuredClone(result);
  Object.assign(data.run_record.metrics.trip_evaluation.driving, {
    extra_duration_seconds: -300,
    extra_distance_meters: -1609.344,
  });
  data.explanation.candidates[0].utility = null;
  render(<TripStats result={data} />);
  expect(figure('Extra driving')).toHaveTextContent('−5 min');
  expect(figure('Extra distance')).toHaveTextContent('-1 mi');
  expect(screen.getByRole('group', { name: 'Museum match' })).toHaveTextContent('—');
});

it('does not relabel historical objective scores or thresholds as match measurements', () => {
  const data = structuredClone(result);
  delete data.run_record;
  data.explanation.solver = { status: 'OPTIMAL', objective_value: 123456, utility_threshold: 0.6 };
  render(<TripStats result={data} />);
  expect(figure('Match estimate')).toHaveTextContent('—');
  expect(screen.getByRole('group', { name: 'Match estimates' })).not.toHaveTextContent('60%');
  expect(screen.queryByText(/123,456|OPTIMAL|CP-SAT|JSON/)).not.toBeInTheDocument();
});

it('keeps daily active time and incomplete days distinct from overnight rest', () => {
  const data = structuredClone(result);
  data.run_record.metrics.trip_evaluation.scenario_target = {
    daily_active_seconds: { 1: 32400, 2: null, 3: 0 },
  };
  render(<TripStats result={data} />);
  const days = screen.getByRole('group', { name: 'Daily driving, visits and waiting' });
  expect(days).toHaveTextContent('Day 19 hrDay 2—Day 30 min');
});
