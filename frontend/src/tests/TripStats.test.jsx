import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import TripStats from '../pages/AlgorithmLab/TripStats';

import result from './fixtures/studioStats';

const figure = (label) => screen.getByText(label, { selector: 'dt' }).nextElementSibling;

it('keeps delivered and selected measures separate in a compact research summary', () => {
  render(<TripStats result={result} />);
  expect(figure('Attractions')).toHaveTextContent('2 / 4');
  expect(figure('Chosen')).toHaveTextContent('3');
  expect(figure('Utility score')).toHaveTextContent('80%');
  expect(screen.getByRole('group', { name: 'Utility scores' })).toHaveTextContent(
    'Chosen utility score80%'
  );
  expect(screen.queryByRole('region', { name: 'Hotel quotes (USD)' })).not.toBeInTheDocument();
  expect(screen.queryByRole('list', { name: 'Place matches' })).not.toBeInTheDocument();
  expect(screen.queryByText('AI requests')).not.toBeInTheDocument();
});

it('compares actual road values and retains solver and end-to-end runtime', () => {
  const data = structuredClone(result);
  data.run_record.metrics.trip_evaluation.driving_gaps = { maximum_attraction_gap_seconds: 18000 };
  render(<TripStats result={data} />);
  expect(screen.getByRole('group', { name: 'Driving time' })).toHaveTextContent(
    'Direct2 hrWith stops3 hr'
  );
  expect(figure('Extra distance')).toHaveTextContent('10 mi');
  expect(figure('Longest gap')).toHaveTextContent('5 hr');
  expect(figure('Extra driving')).toHaveTextContent('1 hr');
  expect(figure('Planning time')).toHaveTextContent('2 min 30 sec');
  expect(figure('Selection time')).toHaveTextContent('4 ms');
});

it('preserves unknowns and measured zeros without inventing research results', () => {
  render(
    <TripStats
      result={{
        run_record: { metrics: { trip_evaluation: { driving: { extra_duration_seconds: 0 } } } },
      }}
    />
  );
  expect(figure('Attractions')).toHaveTextContent('— / —');
  expect(figure('Utility score')).toHaveTextContent('—');
  expect(figure('Extra driving')).toHaveTextContent('0 min');
  expect(figure('Considered')).toHaveTextContent('—');
});

it('keeps signed detours and does not reinterpret historical objective values as utility scores', () => {
  const data = structuredClone(result);
  data.run_record.metrics.trip_evaluation.driving.extra_duration_seconds = -300;
  data.run_record.metrics.trip_evaluation.driving.extra_distance_meters = -1609.344;
  delete data.run_record.metrics.trip_evaluation.utility;
  data.explanation.solver = { objective_value: 123456, utility_threshold: 0.6 };
  render(<TripStats result={data} />);
  expect(figure('Extra driving')).toHaveTextContent('−5 min');
  expect(figure('Extra distance')).toHaveTextContent('-1 mi');
  expect(figure('Utility score')).toHaveTextContent('—');
  expect(screen.getByRole('group', { name: 'Utility scores' })).not.toHaveTextContent('60%');
  expect(screen.queryByText(/123,456|OPTIMAL|CP-SAT|JSON/)).not.toBeInTheDocument();
});
