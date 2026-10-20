import { expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import LabResults from '../pages/AlgorithmLab/LabResults';

vi.mock('../components/Map', () => ({ default: () => <div>Map</div> }));

it.each([
  [{ utility_threshold: 0, utility_threshold_inclusive: false }, '> 0'],
  [{ utility_threshold: 0.6 }, '≥ 0.6'],
])('does not reinterpret saved eligibility thresholds as match percentages', (policy, label) => {
  render(
    <LabResults
      result={{
        mode: 'live',
        snapshot: { label: 'Saved result', source: 'Catalog' },
        explanation: { candidates: [], solver: { status: 'OPTIMAL', ...policy } },
        stages: [],
        input_snapshot: {},
        route: null,
        itinerary: null,
      }}
    />
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Trip stats' }));
  expect(screen.queryByText(label)).not.toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Utility scores' })).toHaveTextContent('—');
});
