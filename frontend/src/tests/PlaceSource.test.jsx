import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PlaceSource from '../components/PlaceSource.jsx';
import ItineraryDays from '../components/ItineraryDays';
import RouteOverview from '../pages/AlgorithmLab/RouteOverview';
import LabResults from '../pages/AlgorithmLab/LabResults';
import { placeSourceLines } from '../components/placeSource.js';

vi.mock('../components/Map', () => ({ default: () => <div>Map</div> }));
const source = {
  source: 'overture',
  source_release: '2026-09-23.1',
  source_attribution: 'Overture Maps Foundation; example contributor',
  source_updated_at: '2026-09-20T23:00:00-07:00',
};
it('shows source attribution, release and evidence date without claiming live availability', () => {
  render(<PlaceSource place={source} />);
  expect(screen.queryByText(/Source: Overture Maps Foundation/)).not.toBeInTheDocument();
  expect(screen.queryByText('Source release: 2026-09-23.1')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Sources' })).toHaveAttribute(
    'href',
    '/catalog-attribution.html'
  );
  expect(screen.queryByText('Source evidence updated: 2026-09-21 (UTC)')).not.toBeInTheDocument();
  expect(screen.queryByText(/current availability are unverified/)).not.toBeInTheDocument();
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
  expect(screen.queryByText('Source: <img src=x onerror=alert(1)>')).not.toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});
it('preserves source context for route stops and evening itinerary suggestions', () => {
  const { rerender } = render(<RouteOverview route={{ stops: [{ name: 'Museum', ...source }] }} />);
  expect(screen.getByLabelText('Place sources')).toBeInTheDocument();
  rerender(
    <ItineraryDays
      itinerary={[
        { date: '2026-10-15', stops: [{ name: 'Cafe', time: '18:00', optional: true, ...source }] },
      ]}
    />
  );
  expect(screen.getByLabelText('Place sources')).toBeInTheDocument();
});
it('keeps source attribution on the route while stats show match estimates', async () => {
  render(
    <LabResults
      result={{
        mode: 'live',
        snapshot: { label: 'Catalog', source: 'Overture' },
        stages: [],
        route: { stops: [{ name: 'Museum', ...source }] },
        explanation: {
          candidates: [
            {
              name: 'Museum',
              utility: 0.75,
              provider_id: 'overture:1',
              ...source,
              provenance: { ratings: 'AI estimate' },
            },
          ],
        },
      }}
    />
  );
  expect(screen.queryByText('Source release: 2026-09-23.1')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('tab', { name: 'Trip stats' }));
  expect(screen.getByRole('group', { name: 'Museum match' })).toHaveTextContent('75%');
  expect(screen.queryByText(/"ratings": "AI estimate"/)).not.toBeInTheDocument();
});
