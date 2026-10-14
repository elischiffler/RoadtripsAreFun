import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PlaceSource from '../components/PlaceSource';
import ItineraryDays from '../components/ItineraryDays';
import RouteOverview from '../pages/AlgorithmLab/RouteOverview';
import LabResults from '../pages/AlgorithmLab/LabResults';
import { placeSourceLines } from '../components/placeSource';

vi.mock('../components/Map', () => ({ default: () => <div>Map</div> }));
const source = {
  source: 'overture',
  source_release: '2026-09-23.1',
  source_attribution: 'Overture Maps Foundation; example contributor',
  source_updated_at: '2026-09-20T23:00:00-07:00',
};
it('shows source attribution, release and evidence date without claiming live availability', () => {
  render(<PlaceSource place={source} />);
  expect(screen.getByText(/Source: Overture Maps Foundation/)).toBeInTheDocument();
  expect(screen.getByText('Source release: 2026-09-23.1')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Data licenses and attribution' })).toHaveAttribute(
    'href',
    '/catalog-attribution.html'
  );
  expect(screen.getByText('Source evidence updated: 2026-09-21 (UTC)')).toBeInTheDocument();
  expect(screen.getByText(/current availability are unverified/)).toBeInTheDocument();
});
it('does not invent catalog provenance for historical records or invalid dates', () => {
  const { container } = render(<PlaceSource place={{ name: 'Old stop', source: 'terra' }} />);
  expect(container).toBeEmptyDOMElement();
  expect(placeSourceLines({ ...source, source_updated_at: 'unknown' })).toContain(
    'Source evidence date unknown'
  );
  expect(placeSourceLines({ ...source, source_updated_at: null })).toContain(
    'Source evidence date unknown'
  );
});
it('escapes source text instead of executing source markup', () => {
  render(<PlaceSource place={{ source_attribution: '<img src=x onerror=alert(1)>' }} />);
  expect(screen.getByText('Source: <img src=x onerror=alert(1)>')).toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});
it('preserves source context for route stops and evening itinerary suggestions', () => {
  const { rerender } = render(<RouteOverview route={{ stops: [{ name: 'Museum', ...source }] }} />);
  expect(screen.getByLabelText('Place source and freshness')).toBeInTheDocument();
  rerender(
    <ItineraryDays
      itinerary={[
        { date: '2026-10-15', stops: [{ name: 'Cafe', time: '18:00', optional: true, ...source }] },
      ]}
    />
  );
  expect(screen.getByLabelText('Place source and freshness')).toBeInTheDocument();
});
it('renders catalog evidence alongside candidate scoring without changing saved provenance', async () => {
  render(
    <LabResults
      result={{
        mode: 'live',
        snapshot: { label: 'Catalog', source: 'Overture' },
        stages: [],
        explanation: {
          candidates: [
            {
              name: 'Museum',
              provider_id: 'overture:1',
              ...source,
              provenance: { ratings: 'AI estimate' },
            },
          ],
        },
      }}
    />
  );
  await userEvent.click(screen.getByRole('tab', { name: 'Algorithm details' }));
  expect(screen.getByText('Source release: 2026-09-23.1')).toBeInTheDocument();
  expect(screen.getByText(/"ratings": "AI estimate"/)).toBeInTheDocument();
});
