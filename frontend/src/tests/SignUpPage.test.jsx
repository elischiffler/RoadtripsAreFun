/**
 * SignUpPage — form rendering, validation, and two-phase sign-up tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderPage } from './testUtils';
import SignUpPage from '../pages/AuthPages/SignUpPage';
import LoginPage from '../pages/AuthPages/LoginPage';
import { Route, Routes, useLocation } from 'react-router-dom';
import { renderWithProviders } from './testUtils';

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
  it('shows an inline error when passwords do not match', async () => {
    const user = userEvent.setup();
    renderPage('/signup', <SignUpPage />);

    await user.type(screen.getByLabelText(/^email/i), 'a@b.com');
    const [pwdInput, confirmInput] = document.querySelectorAll('input[type="password"]');
    await user.type(pwdInput, 'Abc123!x');
    await user.type(confirmInput, 'different1!');
    await user.click(screen.getByRole('button', { name: /sign up/i }));

    expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match.');
    expect(window.alert).not.toHaveBeenCalled();
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
    expect(screen.getByLabelText(/confirmation code/i)).toHaveFocus();
    expect(screen.queryByLabelText(/^email/i)).not.toBeInTheDocument();
    expect(document.querySelectorAll('input[type="password"]')).toHaveLength(0);
    expect(screen.queryByText('Password requirements')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Code sent to a@b.com.');
    expect(window.alert).not.toHaveBeenCalled();
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

const fillSignup = async (user) => {
  await user.type(screen.getByLabelText(/^email/i), 'a@b.com');
  const [password, confirmation] = document.querySelectorAll('input[type="password"]');
  await user.type(password, 'Abc123!x');
  await user.type(confirmation, 'Abc123!x');
};

it('keeps detailed password guidance available on demand', async () => {
  renderPage('/signup', <SignUpPage />);
  const details = document.querySelector('details');
  expect(details.open).toBe(false);
  expect(document.querySelector('input[autocomplete="new-password"]')).toHaveAccessibleDescription(
    '8+ characters with uppercase, lowercase, a number and a symbol.'
  );
  await userEvent.click(screen.getByText('Password requirements'));
  expect(details.open).toBe(true);
  expect(screen.getByText('At least one uppercase letter')).toBeVisible();
});

it('keeps sign-up pending and prevents duplicate submissions before showing a safe retry error', async () => {
  let reject;
  signUp.mockImplementationOnce(
    () =>
      new Promise((resolve, fail) => {
        reject = fail;
      })
  );
  const user = userEvent.setup();
  renderPage('/signup', <SignUpPage />);
  await fillSignup(user);
  await user.click(screen.getByRole('button', { name: 'Sign Up' }));
  expect(screen.getByRole('button', { name: 'Creating account…' })).toBeDisabled();
  expect(screen.getByLabelText(/^email/i)).toBeDisabled();
  fireEvent.submit(document.querySelector('form'));
  expect(signUp).toHaveBeenCalledTimes(1);
  await act(async () => reject(new Error('provider-private-details')));
  expect(screen.getByRole('alert')).toHaveTextContent('Account could not be created. Try again.');
  expect(screen.queryByText('provider-private-details')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign Up' })).toBeEnabled();
});

it('keeps a failed confirmation in the compact phase with an inline error', async () => {
  signUp.mockResolvedValueOnce({ Username: 'uuid-1234' });
  confirmSignUp.mockRejectedValueOnce(new Error('private provider detail'));
  const user = userEvent.setup();
  renderPage('/signup', <SignUpPage />);
  await fillSignup(user);
  await user.click(screen.getByRole('button', { name: 'Sign Up' }));
  await user.type(await screen.findByLabelText(/confirmation code/i), '123456');
  await user.click(screen.getByRole('button', { name: 'Confirm Account' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Code could not be confirmed. Try again.'
  );
  expect(screen.getByLabelText(/confirmation code/i)).toHaveValue('123456');
  expect(screen.queryByLabelText(/^email/i)).not.toBeInTheDocument();
  expect(window.alert).not.toHaveBeenCalled();
});

function PlanningReturn() {
  const location = useLocation();
  return <p>Returned to planning{location.search}</p>;
}

it.each(['/plan?draft=retained', 'https://untrusted.example/elsewhere'])(
  'preserves a sanitized trip return through sign-up, confirmation and login: %s',
  async (returnTo) => {
    const { signIn } = await import('../services/authService');
    signUp.mockResolvedValueOnce({ Username: 'uuid-1234' });
    confirmSignUp.mockResolvedValueOnce(true);
    signIn.mockResolvedValueOnce({ AccessToken: 'fixture' });
    const user = userEvent.setup();
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignUpPage />} />
        <Route path="/plan" element={<PlanningReturn />} />
      </Routes>,
      { initialPath: { pathname: '/login', state: { returnTo } } }
    );
    expect(screen.getByRole('heading', { name: 'Plan your trip' })).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Sign up' }));
    await fillSignup(user);
    await user.click(screen.getByRole('button', { name: 'Sign Up' }));
    await user.type(await screen.findByLabelText(/confirmation code/i), '123456');
    await user.click(screen.getByRole('button', { name: 'Confirm Account' }));
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Account created. Log in to plan your trip.'
    );
    await user.type(screen.getByLabelText(/email/i), 'a@b.com');
    await user.type(document.querySelector('input[type="password"]'), 'Abc123!x');
    await user.click(screen.getByRole('button', { name: 'Log In' }));
    expect(
      await screen.findByText(
        returnTo.startsWith('/plan?')
          ? 'Returned to planning?draft=retained'
          : 'Returned to planning'
      )
    ).toBeInTheDocument();
    expect(window.alert).not.toHaveBeenCalled();
  }
);
