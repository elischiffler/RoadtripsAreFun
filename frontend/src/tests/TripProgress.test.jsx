import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import TripProgress from '../pages/ChatPage/TripProgress';
import { updateTripProgress } from '../pages/ChatPage/tripProgressState';

const event = (stage, state, details = {}) => ({ type: 'progress', stage, state, ...details });
afterEach(() => vi.useRealTimers());

describe('trip progress display', () => {
  it('tracks nested work, repeated searches and terminal failures without exposing unknown internals', () => {
    let progress = { startedAt: 1000, entries: [] };
    progress = updateTripProgress(progress, event('route.schedule', 'started'));
    progress = updateTripProgress(progress, event('hotels.lookup', 'started'));
    progress = updateTripProgress(progress, event('hotels.lookup', 'completed'));
    expect(progress.entries[0].state).toBe('started');
    expect(progress.entries[1].state).toBe('completed');
    progress = updateTripProgress(progress, event('hotels.lookup', 'started'));
    progress = updateTripProgress(progress, event('hotels.lookup', 'failed'));
    expect(progress.entries.map((entry) => entry.state)).toEqual([
      'started',
      'completed',
      'failed',
    ]);
    expect(updateTripProgress(progress, event('secret.raw', 'started'))).toBe(progress);
    expect(updateTripProgress(progress, { type: 'heartbeat' })).toBe(progress);
    for (let i = 0; i < 20; i++)
      progress = updateTripProgress(progress, event('agent.model', 'completed'));
    expect(progress.entries).toHaveLength(12);
  });

  it('shows actual active work, expandable history, and elapsed time with timer cleanup', () => {
    vi.useFakeTimers();
    vi.setSystemTime(1000);
    let progress = { startedAt: 1000, entries: [] };
    progress = updateTripProgress(progress, event('agent.extract_details', 'started'));
    progress = updateTripProgress(progress, event('agent.extract_details', 'completed'));
    progress = updateTripProgress(progress, event('hotels.lookup', 'started'));
    const { unmount } = render(<TripProgress progress={progress} />);
    expect(screen.getByRole('status')).toHaveTextContent('Finding hotels near your route');
    fireEvent.click(screen.getByText('View progress'));
    expect(screen.getByText('Checking your trip details')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getByText('In progress')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(65000));
    expect(screen.getByText('1m 5s elapsed')).toBeInTheDocument();
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('has a safe initial label for legacy loading bubbles', () => {
    render(<TripProgress />);
    expect(screen.getByRole('status')).toHaveTextContent('Getting started');
  });
});
