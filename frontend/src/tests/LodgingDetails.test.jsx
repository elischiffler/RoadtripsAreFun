import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import PlaceTiming from '../components/PlaceTiming.jsx';
const lodging = {
  check_in_date: '2027-06-01',
  check_out_date: '2027-06-03',
  nights: 2,
  planned_arrival: '2027-06-02T06:00:00-06:00',
  planned_departure: '2027-06-02T20:00:00-06:00',
  access_status: 'confirmation_required',
  notice: 'Confirm daytime arrival and departure access with the property before booking.',
};
const hotel = {
  type: 'hotel',
  timezone: 'America/Denver',
  arrival_time: lodging.planned_arrival,
  departure_time: lodging.planned_departure,
  lodging,
};
it('keeps the actual daytime rest clocks separate from the full quoted calendar period', () => {
  render(<PlaceTiming place={hotel} />);
  expect(screen.getByText('Planned arrival')).toBeInTheDocument();
  expect(screen.getByText('Planned departure')).toBeInTheDocument();
  expect(screen.getByLabelText('Jun 2, 2027, 6:00 AM GMT-6 (America/Denver)')).toHaveAttribute(
    'datetime',
    hotel.arrival_time
  );
  const quote = screen.getByRole('region', { name: 'Hotel quote dates' });
  expect(quote).toHaveTextContent('2 nights');
  expect(within(quote).getByLabelText('Quoted check-in: Jun 1, 2027')).toHaveAttribute(
    'datetime',
    '2027-06-01'
  );
  expect(within(quote).getByLabelText('Quoted check-out: Jun 3, 2027')).toHaveAttribute(
    'datetime',
    '2027-06-03'
  );
  expect(quote).toHaveTextContent('Confirm daytime arrival and departure access');
  expect(within(quote).queryByText(/confirmed|booked/i)).not.toBeInTheDocument();
});
it('leaves legacy hotel display intact and never invents quote dates from its arrival', () => {
  render(<PlaceTiming place={{ ...hotel, lodging: undefined }} />);
  expect(screen.getByText('Arrival')).toBeInTheDocument();
  expect(screen.getByText('Leaving')).toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Hotel quote dates' })).not.toBeInTheDocument();
});
it('does not invent a physical arrival clock from quoted dates when actual timing is missing', () => {
  render(<PlaceTiming place={{ lodging }} />);
  expect(screen.getByRole('region', { name: 'Hotel quote dates' })).toHaveTextContent('2 nights');
  expect(screen.queryByText('Planned arrival')).not.toBeInTheDocument();
  expect(screen.queryByText('6:00 AM')).not.toBeInTheDocument();
});
it.each([
  { ...lodging, nights: 1 },
  { ...lodging, check_out_date: '2027-02-30' },
  { ...lodging, access_status: 'confirmed' },
])('handles inconsistent quote metadata without an availability claim', (value) => {
  render(<PlaceTiming place={{ ...hotel, lodging: value }} />);
  const quote = screen.getByRole('region', { name: 'Hotel quote dates' });
  expect(quote).toHaveTextContent('Quote dates are unavailable');
  expect(within(quote).queryByRole('time')).not.toBeInTheDocument();
});
