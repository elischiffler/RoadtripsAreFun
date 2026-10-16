import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderPage } from './testUtils';
import HomePage from '../pages/HomePage/HomePage';

describe('HomePage', () => {
  it('provides separate setup, research and saved-trip destinations', () => {
    renderPage('/', <HomePage />);
    expect(
      screen.getByRole('heading', { name: 'The journey is part of the trip.' })
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Plan a trip/ })).toHaveAttribute('href', '/plan');
    expect(screen.getByRole('link', { name: /AI Studio/ })).toHaveAttribute('href', '/studio');
    expect(screen.getByRole('link', { name: 'Open saved trips' })).toHaveAttribute(
      'href',
      '/trips'
    );
  });
});
