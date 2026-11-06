import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ItineraryDays from '../components/ItineraryDays';
import RouteOverview from '../pages/AlgorithmLab/RouteOverview';

vi.mock('../components/Map', () => ({ default: () => <div>Map</div> }));
it('keeps source metadata off place cards without changing the saved record', () => {
  const place = {
    name: 'Museum',
    type: 'stop',
    source_attribution: 'Fixture credit',
    source_release: 'fixture-v1',
  };
  const original = structuredClone(place);
  const view = render(<RouteOverview route={{ stops: [place] }} />);
  expect(screen.queryByRole('link', { name: 'Sources' })).not.toBeInTheDocument();
  expect(screen.queryByText(/Fixture credit|fixture-v1|^stop$/)).not.toBeInTheDocument();
  view.rerender(<ItineraryDays itinerary={[{ date: '2030-01-01', stops: [place] }]} />);
  expect(screen.queryByRole('link', { name: 'Sources' })).not.toBeInTheDocument();
  expect(place).toEqual(original);
});
