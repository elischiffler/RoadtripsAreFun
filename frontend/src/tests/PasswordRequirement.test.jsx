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
    renderWithProviders(<PasswordRequirement fulfilled={true} text="One uppercase letter" />);
    expect(screen.getByTestId('password-requirement-check')).toBeInTheDocument();
    expect(screen.queryByTestId('password-requirement-close')).not.toBeInTheDocument();
  });

  it('shows a close icon when not fulfilled', () => {
    renderWithProviders(<PasswordRequirement fulfilled={false} text="One special character" />);
    expect(screen.getByTestId('password-requirement-close')).toBeInTheDocument();
    expect(screen.queryByTestId('password-requirement-check')).not.toBeInTheDocument();
  });
});
