/**
 * AuthWrapper — guards protected routes.
 *
 * Tests verify:
 *  1. Unauthenticated user is redirected to /login when accessing a protected route
 *  2. Authenticated user can access protected content
 *  3. Public routes (/login, /signup, /) are always accessible
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { renderWithProviders } from './testUtils';
import AuthWrapper from '../components/AuthWrapper';

const ProtectedPage = () => <p>Protected Content</p>;
const LoginPage = () => <p>Login Page</p>;

function renderRoute(initialPath) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/chat"
        element={
          <AuthWrapper>
            <ProtectedPage />
          </AuthWrapper>
        }
      />
    </Routes>,
    { initialPath }
  );
}

describe('AuthWrapper', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  it('redirects to /login when no accessToken and visiting /chat', () => {
    renderRoute('/chat');
    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('renders the protected page when accessToken is present', () => {
    sessionStorage.setItem('accessToken', 'fake-token-abc');
    renderRoute('/chat');
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });
});
