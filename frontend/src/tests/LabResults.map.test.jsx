import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import mapboxgl from 'mapbox-gl';
import LabResults from '../pages/AlgorithmLab/LabResults';

vi.mock('mapbox-gl', () => ({
  default: {
    Map: vi.fn(() => ({ on: vi.fn(), addControl: vi.fn(), remove: vi.fn() })),
    AttributionControl: vi.fn(),
  },
}));

function run(id, coordinates) {
  return {
    mode: 'live',
    snapshot: { id, label: 'Live discovery', source: 'Provider response' },
    explanation: { weights: {}, candidates: [], solver: null },
    stages: [],
    input_snapshot: {},
    route: { geometry: { coordinates }, distance: 10000, duration: 3600, cost: 0 },
    itinerary: null,
  };
}

describe('Lab map lifecycle', () => {
  it('recreates the shared map for the next live run even without a pending render', () => {
    const view = render(
      <LabResults
        result={run('live-one', [
          [-122, 37],
          [-121, 36],
        ])}
      />
    );
    expect(mapboxgl.Map).toHaveBeenCalledTimes(1);
    const previousMap = mapboxgl.Map.mock.results[0].value;
    view.rerender(
      <LabResults
        result={run('live-two', [
          [-120, 35],
          [-119, 34],
        ])}
      />
    );
    expect(previousMap.remove).toHaveBeenCalledOnce();
    expect(mapboxgl.Map).toHaveBeenCalledTimes(2);
    expect(mapboxgl.Map.mock.calls[1][0].center).toEqual([-119.5, 34.5]);
  });
});
