/**
 * SignUpPage — form rendering, validation, and two-phase sign-up tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderPage } from './testUtils';
import SignUpPage from '../pages/AuthPages/SignUpPage';

vi.mock('../services/authService', () => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
}));

import { signUp, confirmSignUp } from '../services/authService';

// Suppress alert() noise in test output
beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

describe('SignUpPage — initial render', () => {
  it('shows the "Create Your Account" heading', () => {
    renderPage('/signup', <SignUpPage />);
    expect(screen.getByText(/create your account/i)).toBeInTheDocument();
  });

  it('renders email, password, confirm-password fields and a Sign Up button', () => {
    renderPage('/signup', <SignUpPage />);
    expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
    // Two password-type inputs: Password and Confirm Password
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    expect(passwordInputs).toHaveLength(2);
    expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument();
  });

  it('renders all 5 password requirement indicators', () => {
    renderPage('/signup', <SignUpPage />);
    expect(screen.getByText(/at least one uppercase letter/i)).toBeInTheDocument();
    expect(screen.getByText(/at least one lowercase letter/i)).toBeInTheDocument();
    expect(screen.getByText(/at least one number/i)).toBeInTheDocument();
    expect(screen.getByText(/at least one special character/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 8 characters long/i)).toBeInTheDocument();
  });
});

describe('SignUpPage — password mismatch', () => {
  it('alerts when passwords do not match', async () => {
    const user = userEvent.setup();
    renderPage('/signup', <SignUpPage />);

    await user.type(screen.getByLabelText(/^email/i), 'a@b.com');
    const [pwdInput, confirmInput] = document.querySelectorAll('input[type="password"]');
    await user.type(pwdInput, 'Abc123!x');
    await user.type(confirmInput, 'different1!');
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    expect(window.alert).toHaveBeenCalledWith('Passwords do not match!');
    expect(signUp).not.toHaveBeenCalled();
  });
});

describe('SignUpPage — phase 1 → phase 2 transition', () => {
  it('moves to the confirmation-code phase after successful signUp', async () => {
    signUp.mockResolvedValueOnce({ Username: 'uuid-1234' });
    const user = userEvent.setup();
    renderPage('/signup', <SignUpPage />);

    await user.type(screen.getByLabelText(/^email/i), 'a@b.com');
    const [pwdInput, confirmInput] = document.querySelectorAll('input[type="password"]');
    await user.type(pwdInput, 'Abc123!x');
    await user.type(confirmInput, 'Abc123!x');
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    await waitFor(() => {
      expect(screen.getByText(/confirm your account/i)).toBeInTheDocument();
    });

    // Confirmation code field should now be visible
    expect(screen.getByLabelText(/confirmation code/i)).toBeInTheDocument();
  });
});

describe('SignUpPage — phase 2: confirm account', () => {
  it('calls confirmSignUp with the entered code', async () => {
    // Start from confirmation phase
    signUp.mockResolvedValueOnce({ Username: 'uuid-1234' });
    confirmSignUp.mockResolvedValueOnce(true);
    const user = userEvent.setup();
    renderPage('/signup', <SignUpPage />);

    // Complete phase 1
    await user.type(screen.getByLabelText(/^email/i), 'a@b.com');
    const [pwdInput, confirmInput] = document.querySelectorAll('input[type="password"]');
    await user.type(pwdInput, 'Abc123!x');
    await user.type(confirmInput, 'Abc123!x');
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    // Phase 2
    await waitFor(() => screen.getByLabelText(/confirmation code/i));
    await user.type(screen.getByLabelText(/confirmation code/i), '123456');
    await user.click(screen.getByRole('button', { name: /confirm account/i }));

    await waitFor(() => {
      expect(confirmSignUp).toHaveBeenCalledWith('uuid-1234', '123456');
    });
  });
});
