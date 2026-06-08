/**
 * GlobalHeader — top navigation bar tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderWithProviders } from './testUtils';
import GlobalHeader from '../components/GlobalHeader';

describe('GlobalHeader', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  it('is hidden on the /login route', () => {
    renderWithProviders(<GlobalHeader />, { initialPath: '/login' });
    // The header returns null on /login — nothing should render
    expect(document.querySelector('.global-header')).not.toBeInTheDocument();
  });

  it('is hidden on the /signup route', () => {
    renderWithProviders(<GlobalHeader />, { initialPath: '/signup' });
    expect(document.querySelector('.global-header')).not.toBeInTheDocument();
  });

  it('shows a Login button when unauthenticated', () => {
    renderWithProviders(<GlobalHeader />, { initialPath: '/' });
    expect(screen.getByRole('link', { name: /login/i })).toBeInTheDocument();
  });

  it('shows the avatar when authenticated', () => {
    sessionStorage.setItem('accessToken', 'fake-token');
    renderWithProviders(<GlobalHeader />, { initialPath: '/chat' });
    // The avatar renders a "U" placeholder
    expect(screen.getByText('U')).toBeInTheDocument();
  });

  it('clears tokens and closes menu on Sign out click', async () => {
    sessionStorage.setItem('accessToken', 'fake-token');
    sessionStorage.setItem('idToken', 'id-tok');
    sessionStorage.setItem('refreshToken', 'ref-tok');
    const user = userEvent.setup();

    renderWithProviders(<GlobalHeader />, { initialPath: '/chat' });

    // Open profile menu
    await user.click(screen.getByText('U'));
    // Click Sign out
    await user.click(screen.getByText(/sign out/i));

    await waitFor(() => {
      expect(sessionStorage.getItem('accessToken')).toBeNull();
      expect(sessionStorage.getItem('idToken')).toBeNull();
      expect(sessionStorage.getItem('refreshToken')).toBeNull();
    });
  });
});
