import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TripPage from '../pages/TripPage/TripPage';
import { useStoredTrip } from '../pages/useStoredTrip';
vi.mock('../components/Map', () => ({ default: () => <div>Map preview</div> }));
vi.mock('../pages/useStoredTrip', () => ({ useStoredTrip: vi.fn() }));
vi.mock('../components/TripVisitProgress', () => ({
  default: () => <div>Saved itinerary stops</div>,
}));
const show = (trip) => {
  useStoredTrip.mockReturnValue({
    currentId: 1,
    getChatDataById: () => trip,
    chatdata: trip ? [trip] : [],
  });
  render(
    <MemoryRouter>
      <TripPage />
    </MemoryRouter>
  );
};
describe('trip workspace', () => {
  it('offers saved trips without a selection', () => {
    show(null);
    expect(screen.getByRole('heading', { name: 'No trip selected' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Saved trips' })).toHaveAttribute('href', '/trips');
  });
  it('shows necessary facts and separate map and editor links with scrollable itinerary', () => {
    show({
      chatId: 1,
      startConfirmed: { address: 'Los Angeles' },
      endConfirmed: { address: 'San Diego' },
      itinerary: [{ date: '2026-12-01' }, { date: '2026-12-02' }],
      route: {
        duration: 7200,
        distance: 160934,
        geometry: {
          coordinates: [
            [-118, 34],
            [-117, 33],
          ],
        },
      },
    });
    expect(screen.getByText('Los Angeles')).toBeInTheDocument();
    expect(screen.getByText('San Diego')).toBeInTheDocument();
    expect(screen.getByText('2026-12-01 – 2026-12-02')).toBeInTheDocument();
    expect(screen.getByText('2h 0m')).toBeInTheDocument();
    expect(screen.getByText('100 miles')).toBeInTheDocument();
    expect(document.querySelector('.trip-map-preview-link')).toHaveAttribute('href', '/map');
    expect(
      screen
        .getAllByRole('link', { name: 'Edit itinerary' })
        .every((link) => link.getAttribute('href') === '/itinerary/edit')
    ).toBe(true);
    expect(screen.getByRole('region', { name: 'Trip itinerary' })).toHaveAttribute('tabindex', '0');
  });
  it('keeps partial trip details usable without inventing dates or distance', () => {
    show({ chatId: 1, startConfirmed: { address: 'Boston' } });
    expect(screen.getByText('Boston')).toBeInTheDocument();
    expect(screen.getByText('No route available.')).toBeInTheDocument();
    expect(screen.queryByText('Dates')).not.toBeInTheDocument();
  });
});
