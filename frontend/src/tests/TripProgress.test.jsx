import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import TripProgress from '../pages/ChatPage/TripProgress';
import { updateTripProgress } from '../pages/ChatPage/tripProgressState';

const event = (stage, state, details = {}) => ({ type: 'progress', stage, state, ...details });

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

  it('shows only the current step and returns to Thinking between steps', () => {
    let progress = { entries: [] };
    progress = updateTripProgress(progress, event('agent.extract_details', 'started'));
    progress = updateTripProgress(progress, event('agent.extract_details', 'completed'));
    progress = updateTripProgress(progress, event('hotels.lookup', 'started'));
    const { rerender, container } = render(<TripProgress progress={progress} />);
    expect(screen.getByRole('status')).toHaveTextContent('Finding hotels near your route…');
    expect(container.textContent).toBe('Finding hotels near your route…');
    progress = updateTripProgress(progress, event('hotels.lookup', 'completed'));
    rerender(<TripProgress progress={progress} />);
    expect(screen.getByRole('status')).toHaveTextContent('Thinking…');
  });

  it('has a safe initial label for legacy loading bubbles', () => {
    render(<TripProgress />);
    expect(screen.getByRole('status')).toHaveTextContent('Thinking…');
  });
});
