import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import ItineraryDays from '../components/ItineraryDays';

const lunch = {
  id: 'meal:2030-11-03:lunch',
  kind: 'meal',
  name: 'Lunch',
  status: 'reserved',
  arrival_time: '2030-11-03T12:15:00-08:00',
  departure_time: '2030-11-03T13:00:00-08:00',
  window_start: '2030-11-03T12:00:00-08:00',
  window_end: '2030-11-03T14:00:00-08:00',
  timezone: 'America/Los_Angeles',
  notice: 'No stopping location is verified. Allow extra time for parking or a detour.',
};

it('shows actual scheduled meal time and duration without dining bookings or visit controls', () => {
  render(
    <ItineraryDays
      itinerary={[{ date: 'Sunday, November 03 2030', stops: [lunch] }]}
      onToggleVisited={() => {}}
    />
  );
  const breaks = screen.getByRole('region', { name: 'Meal breaks' });
  expect(breaks).toHaveTextContent('12:15 PM');
  expect(breaks).toHaveTextContent('1:00 PM');
  expect(breaks).toHaveTextContent('45 minutes set aside');
  expect(breaks).toHaveTextContent('No dining place is selected or booked.');
  expect(breaks).toHaveTextContent('No stopping location is verified.');
  expect(within(breaks).queryByRole('button')).not.toBeInTheDocument();
  expect(screen.queryByRole('region', { name: 'Open meal windows' })).not.toBeInTheDocument();
});

it('keeps historical advisory windows separate from real meal breaks', () => {
  render(
    <ItineraryDays
      itinerary={[
        {
          date: 'Sunday, November 03 2030',
          stops: [
            lunch,
            {
              kind: 'meal',
              name: 'Dinner',
              time: 'Unscheduled',
              status: 'open',
              window_start: '2030-11-03T18:00:00-08:00',
              window_end: '2030-11-03T20:00:00-08:00',
            },
          ],
        },
      ]}
    />
  );
  const open = screen.getByRole('region', { name: 'Open meal windows' });
  expect(open).toHaveTextContent('Dinner');
  expect(open).toHaveTextContent('no time or place is reserved');
  expect(open).not.toHaveTextContent('Lunch');
  expect(screen.getByRole('region', { name: 'Meal breaks' })).not.toHaveTextContent('Dinner');
});

it('does not claim malformed saved reservation intervals are scheduled', () => {
  render(
    <ItineraryDays
      itinerary={[
        {
          date: 'Sunday, November 03 2030',
          stops: [
            { ...lunch, departure_time: lunch.arrival_time },
            { ...lunch, id: 'missing-offset', arrival_time: '2030-11-03T12:15:00' },
          ],
        },
      ]}
    />
  );
  expect(screen.queryByRole('region', { name: 'Meal breaks' })).not.toBeInTheDocument();
  expect(screen.getAllByText(/no usable scheduled interval/)).toHaveLength(2);
  expect(screen.queryByText(/minutes set aside/)).not.toBeInTheDocument();
});
