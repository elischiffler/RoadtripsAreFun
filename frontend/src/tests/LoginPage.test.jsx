/**
 * LoginPage — form rendering and interaction tests.
 * authService is fully mocked so no real Cognito calls happen.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderPage } from './testUtils';
import LoginPage from '../pages/AuthPages/LoginPage';

// Mock the authService so we never hit real Cognito
vi.mock('../services/authService', () => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
}));

import { signIn } from '../services/authService';

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('renders email and password fields plus the Log In button', () => {
    renderPage('/login', <LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    // PasswordField renders a MUI TextField; accessible label text includes the asterisk
    // in an aria-hidden span, so we match loosely on "password"
    expect(screen.getAllByLabelText(/password/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
  });

  it('renders a link to the sign-up page', () => {
    renderPage('/login', <LoginPage />);
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument();
  });

  it('shows an error message on failed sign-in', async () => {
    signIn.mockRejectedValueOnce(new Error('Wrong password'));
    const user = userEvent.setup();

    renderPage('/login', <LoginPage />);
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    const passwordInput = document.querySelector('input[type="password"]');
    await user.type(passwordInput, 'wrongpassword');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByText(/failed to sign in/i)).toBeInTheDocument();
    });
  });

  it('calls signIn with the entered credentials', async () => {
    signIn.mockResolvedValueOnce({ AccessToken: 'tok' });
    const user = userEvent.setup();

    renderPage('/login', <LoginPage />);
    await user.type(screen.getByLabelText(/email/i), 'user@example.com');
    // There is only one password field on the login page — grab by input type
    const passwordInput = document.querySelector('input[type="password"]');
    await user.type(passwordInput, 'MyP@ss1');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(signIn).toHaveBeenCalledWith('user@example.com', 'MyP@ss1');
    });
  });
});
