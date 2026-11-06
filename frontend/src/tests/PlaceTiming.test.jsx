import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import PlaceTiming from '../components/PlaceTiming';
import ItineraryDays from '../components/ItineraryDays';
import RouteOverview from '../pages/AlgorithmLab/RouteOverview';
import { compactTimestamp, localTimestamp } from '../components/placeTiming';

vi.mock('../components/Map', () => ({ default: () => <div>Map</div> }));

const stop = {
  provider_id: 'synthetic:museum',
  type: 'stop',
  name: 'Synthetic museum',
  timezone: 'America/Los_Angeles',
  arrival_time: '2030-11-03T01:30:00-07:00',
  departure_time: '2030-11-03T01:30:00-08:00',
  visit_duration: { seconds: 3600, source: 'ai_estimate' },
};

describe('arrival and leaving display', () => {
  it('keeps repeated DST clocks distinguishable without long visible timestamps', () => {
    render(<PlaceTiming place={stop} />);
    const arrival = screen.getByLabelText('Nov 3, 2030, 1:30 AM GMT-7 (America/Los_Angeles)');
    const leaving = screen.getByLabelText('Nov 3, 2030, 1:30 AM GMT-8 (America/Los_Angeles)');
    expect(arrival).toHaveTextContent('1:30 AM');
    expect(arrival).toHaveAttribute('datetime', stop.arrival_time);
    expect(leaving).toHaveAttribute('datetime', stop.departure_time);
    expect(screen.getByText('Nov 3 · PDT')).toBeInTheDocument();
    expect(screen.getByText('Nov 3 · PST')).toBeInTheDocument();
    expect(screen.queryByText(/America\/Los_Angeles|GMT-7|GMT-8/)).not.toBeInTheDocument();
    expect(screen.queryByText(/AI-estimated visit|Estimated visit/)).not.toBeInTheDocument();
  });

  it('shows midnight and hotel leaving on the next date without an estimate tag', () => {
    render(
      <PlaceTiming
        place={{
          ...stop,
          type: 'hotel',
          arrival_time: '2030-07-01T23:50:00-07:00',
          departure_time: '2030-07-02T09:00:00-07:00',
          visit_duration: { source: 'conservative_fallback' },
        }}
      />
    );
    expect(screen.getByText('11:50 PM')).toBeInTheDocument();
    expect(screen.getByText('9:00 AM')).toBeInTheDocument();
    expect(screen.getByText('Jul 1 · PDT')).toBeInTheDocument();
    expect(screen.getByText('Jul 2 · PDT')).toBeInTheDocument();
  });

  it('shares the date and zone for an ordinary visit and shows missing clocks as unknown', () => {
    const view = render(
      <PlaceTiming
        place={{
          ...stop,
          arrival_time: '2030-07-01T14:00:00-07:00',
          departure_time: '2030-07-01T15:00:00-07:00',
        }}
      />
    );
    expect(screen.getAllByText('Jul 1 · PDT')).toHaveLength(1);
    expect(screen.getByText('2:00 PM')).toBeInTheDocument();
    expect(screen.getByText('3:00 PM')).toBeInTheDocument();
    view.rerender(<PlaceTiming place={{ ...stop, departure_time: null }} />);
    expect(screen.getByLabelText('Unavailable')).toHaveTextContent('—');
    expect(screen.getAllByText('1:30 AM')).toHaveLength(1);
  });

  it('preserves explicit offsets without inventing missing clocks or zones', () => {
    expect(localTimestamp('2030-07-02T00:15:00+05:30')).toBe('2030-07-02 00:15 (UTC+05:30)');
    expect(localTimestamp('2030-07-02T00:15:00Z', 'invalid/zone')).toBe(
      '2030-07-02 00:15 (UTC+00:00)'
    );
    expect(localTimestamp('2030-07-02T00:15')).toBeNull();
    expect(localTimestamp('invalid')).toBeNull();
    expect(compactTimestamp('2030-07-02T00:15:00+05:30')).toMatchObject({
      date: 'Jul 2',
      time: '12:15 AM',
      zone: 'UTC+05:30',
    });
    expect(compactTimestamp('2030-07-02T00:15:00Z', 'invalid/zone')).toMatchObject({
      time: '12:15 AM',
      zone: 'UTC',
    });
    const { container } = render(<PlaceTiming place={{ name: 'Old saved stop' }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows final arrival without suggesting a visit or leaving the destination', () => {
    render(<PlaceTiming place={{ ...stop, type: 'end' }} />);
    expect(screen.getByText('Arrival')).toBeInTheDocument();
    expect(screen.queryByText('Leaving')).not.toBeInTheDocument();
  });

  it('hides only departure rows already paired with a place and keeps saved legacy rows', () => {
    render(
      <ItineraryDays
        itinerary={[
          {
            date: 'November 3',
            stops: [
              { ...stop, time: '01:30 AM' },
              { name: 'Depart from the stop', time: '01:30 AM', paired_departure: true },
              { name: 'Legacy departure', time: '08:00 AM' },
            ],
          },
        ]}
      />
    );
    expect(screen.queryByText('Depart from the stop')).not.toBeInTheDocument();
    expect(screen.getByText('Legacy departure')).toBeInTheDocument();
    expect(screen.getByText('Departure time: 08:00 AM')).toBeInTheDocument();
  });

  it('uses the same clocks in route and itinerary while preserving other card information', () => {
    const place = {
      ...stop,
      source: 'Offline control',
      source_attribution: 'Fixture attribution',
      source_release: 'fixture-v1',
      source_updated_at: '2030-07-01',
      address: '123 Fixture Road',
      url: 'https://example.test/place',
      price: 50,
      notice: 'Reservation required',
      time: '01:30 AM',
      kind: 'arrival',
    };
    const { unmount } = render(<RouteOverview route={{ stops: [place] }} />);
    const times = within(screen.getByLabelText('Place timing'))
      .getAllByText(/^1:30 AM$/)
      .map((node) => node.getAttribute('aria-label'));
    expect(screen.queryByText(/Source: Fixture attribution/)).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sources' })).not.toBeInTheDocument();
    expect(screen.queryByText('stop')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Place')).toHaveClass('lab-stop-dot');
    unmount();
    render(<ItineraryDays itinerary={[{ date: 'November 3, 2030', stops: [place] }]} />);
    expect(
      within(screen.getByLabelText('Place timing'))
        .getAllByText(/^1:30 AM$/)
        .map((node) => node.getAttribute('aria-label'))
    ).toEqual(times);
    expect(screen.getByRole('link', { name: place.name })).toHaveAttribute('href', place.url);
    for (const content of ['Address: 123 Fixture Road', 'Price: $50', 'Reservation required'])
      expect(screen.getByText(content)).toBeInTheDocument();
    expect(screen.queryByText(/^Arrival time:/)).not.toBeInTheDocument();
  });
});
