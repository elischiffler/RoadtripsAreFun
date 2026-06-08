/**
 * InputStops (StopSlider) — pill carousel tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderWithProviders } from './testUtils';
import StopSlider from '../pages/ChatPage/InputStops';

describe('StopSlider', () => {
  const onSelect = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  it('renders pills for 1 through 10', () => {
    renderWithProviders(<StopSlider onSelect={onSelect} />);
    for (let n = 1; n <= 10; n++) {
      expect(
        screen.getByRole('button', { name: new RegExp(`^${n} stops?$`, 'i') })
      ).toBeInTheDocument();
    }
  });

  it('calls onSelect with the correct number when a pill is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StopSlider onSelect={onSelect} />);
    await user.click(screen.getByRole('button', { name: /^3 stops?$/i }));
    expect(onSelect).toHaveBeenCalledWith(3);
  });

  it('marks the clicked pill as selected (aria-pressed)', async () => {
    const user = userEvent.setup();
    renderWithProviders(<StopSlider onSelect={onSelect} />);
    const pill5 = screen.getByRole('button', { name: /^5 stops?$/i });
    await user.click(pill5);
    expect(pill5).toHaveAttribute('aria-pressed', 'true');
  });

  it('starts with pill 1 selected', () => {
    renderWithProviders(<StopSlider onSelect={onSelect} />);
    expect(screen.getByRole('button', { name: /^1 stop$/i })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });
});
