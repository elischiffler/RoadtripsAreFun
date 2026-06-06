/**
 * HomePage — landing page smoke tests.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderPage } from './testUtils';
import HomePage from '../pages/HomePage/HomePage';

describe('HomePage (unauthenticated)', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  it('renders the hero title', () => {
    renderPage('/', <HomePage />);
    expect(screen.getByText('RoadtripsAreFun')).toBeInTheDocument();
  });

  it('renders Login and Sign Up nav buttons', () => {
    renderPage('/', <HomePage />);
    expect(screen.getByRole('link', { name: /login/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument();
  });

  it('renders the "Start Planning" CTA', () => {
    renderPage('/', <HomePage />);
    expect(screen.getByRole('button', { name: /start planning/i })).toBeInTheDocument();
  });

  it('renders feature chip labels', () => {
    renderPage('/', <HomePage />);
    // SpinningWheelChip renders the label text twice (pill + SVG textPath)
    expect(screen.getAllByText(/route generation/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/hotel finder/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/itinerary builder/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('HomePage (authenticated)', () => {
  beforeEach(() => {
    sessionStorage.setItem('accessToken', 'fake-token');
  });
  afterEach(() => sessionStorage.clear());

  it('renders Open App and Logout buttons instead of Login/Sign Up', () => {
    renderPage('/', <HomePage />);
    expect(screen.getByRole('button', { name: /open app/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /login/i })).not.toBeInTheDocument();
  });

  it('clears sessionStorage tokens on Logout click', async () => {
    const user = userEvent.setup();
    renderPage('/', <HomePage />);
    await user.click(screen.getByRole('button', { name: /logout/i }));
    expect(sessionStorage.getItem('accessToken')).toBeNull();
    expect(sessionStorage.getItem('idToken')).toBeNull();
    expect(sessionStorage.getItem('refreshToken')).toBeNull();
  });
});
