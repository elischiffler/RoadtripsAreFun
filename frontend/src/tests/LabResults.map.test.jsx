import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import LabResults from '../pages/AlgorithmLab/LabResults';

const viewer = vi.hoisted(() => vi.fn());
vi.mock('../components/AppleRouteViewer', () => ({ default: viewer }));

function run(id, route) {
  return {
    mode: 'live',
    snapshot: { id, label: 'Live discovery', source: 'Provider response' },
    explanation: { weights: {}, candidates: [], solver: null },
    stages: [],
    input_snapshot: {},
    route,
    itinerary: null,
  };
}
afterEach(() => vi.unstubAllEnvs());

it('renders current and archived Apple Studio routes through the Studio-aware viewer', () => {
  viewer.mockReturnValue(<p>Apple route viewer</p>);
  const coordinates = [
    [37, -122],
    [36, -121],
  ];
  const archived = { directions_provider: 'apple', coordinates, stops: [], cost: 0 };
  const view = render(<LabResults result={run('live-one', archived)} />);
  expect(screen.getByText('Apple route viewer')).toBeVisible();
  expect(viewer.mock.lastCall[0]).toMatchObject({ route: archived, studio: true });
  const current = {
    ...archived,
    geometry: {
      coordinates: [
        [-120, 35],
        [-119, 34],
      ],
    },
  };
  view.rerender(<LabResults result={run('live-two', current)} />);
  expect(viewer.mock.lastCall[0]).toMatchObject({ route: current, studio: true });
});
