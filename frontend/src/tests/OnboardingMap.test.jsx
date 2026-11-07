import { expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import OnboardingMap from '../pages/TripSetup/OnboardingMap';
it('never fabricates coordinates from unconfirmed typed text', () => {
  const view = render(
    <OnboardingMap origin={{ address: 'Springfield' }} destination={{ address: 'Somewhere' }} />
  );
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.getByText('A · Springfield · unconfirmed')).toBeInTheDocument();
  view.rerender(
    <OnboardingMap origin={{ address: 'Verified provider match', latitude: 40, longitude: -105 }} />
  );
  expect(
    screen.getByRole('button', { name: 'Draft location: Verified provider match' })
  ).toBeInTheDocument();
  expect(screen.queryByText('Checked route')).not.toBeInTheDocument();
});
it('distinguishes database ideas and approximate regions from scheduled and checked stops', () => {
  render(
    <OnboardingMap
      phase="checking"
      route={{
        geometry: {
          coordinates: [
            [-105, 40],
            [-104, 40],
          ],
        },
      }}
      ideas={[
        {
          id: 'idea',
          name: 'Catalog trail',
          coordinates: [40, -104.5],
          place_context: { summary: 'Reviewed trail context' },
        },
      ]}
      stayAreas={[{ label: 'Possible rest region', coordinates: [40, -104.3] }]}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Unscheduled idea: Catalog trail' }));
  expect(screen.getByRole('status')).toHaveTextContent('Reviewed trail context');
  expect(screen.getByRole('status')).toHaveTextContent('not scheduled');
  fireEvent.click(screen.getByRole('button', { name: /Approximate rest region/ }));
  expect(screen.getByRole('status')).toHaveTextContent('not a hotel or availability check');
  expect(screen.queryByText('Checked route')).not.toBeInTheDocument();
});

it('uses reviewed route context by provider identity and labels actual hotel options without a booking claim', () => {
  render(
    <OnboardingMap
      phase="confirmed"
      route={{
        geometry: {
          coordinates: [
            [-105, 40],
            [-104, 41],
          ],
        },
        stops: [
          {
            type: 'hotel',
            name: 'Actual hotel option',
            provider_id: 'hotel:1',
            coordinates: [40.5, -104.5],
          },
        ],
        place_context: { 'hotel:1': { summary: 'Reviewed context' } },
      }}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Hotel option: Actual hotel option' }));
  expect(screen.getByRole('status')).toHaveTextContent('Reviewed context');
  expect(screen.getByRole('status')).toHaveTextContent('not booked');
});
