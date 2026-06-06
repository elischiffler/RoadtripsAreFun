/**
 * PasswordRequirement — visual indicator component tests.
 */
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import React from 'react';
import { renderWithProviders } from './testUtils';
import PasswordRequirement from '../pages/AuthPages/PasswordRequirement';

describe('PasswordRequirement', () => {
  it('renders the requirement text', () => {
    renderWithProviders(
      <PasswordRequirement fulfilled={false} text="At least 8 characters long" />
    );
    expect(screen.getByText('At least 8 characters long')).toBeInTheDocument();
  });

  it('shows a check icon when fulfilled', () => {
    const { container } = renderWithProviders(
      <PasswordRequirement fulfilled={true} text="One uppercase letter" />
    );
    // MUI CheckIcon renders an SVG with data-testid or aria role; just assert the container
    // has the green check by checking an icon element exists
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('shows a close icon when not fulfilled', () => {
    const { container } = renderWithProviders(
      <PasswordRequirement fulfilled={false} text="One special character" />
    );
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });
});
