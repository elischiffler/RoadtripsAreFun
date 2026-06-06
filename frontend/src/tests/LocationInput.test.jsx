/**
 * LocationInput — address entry + geolocation button tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderWithProviders } from './testUtils';
import LocationInput from '../pages/ChatPage/LocationInput';

describe('LocationInput', () => {
  const onSubmit = vi.fn();
  const onGeolocate = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  it('renders the text field with the given placeholder', () => {
    renderWithProviders(
      <LocationInput
        placeholder="Enter your starting city…"
        onSubmit={onSubmit}
        onGeolocate={onGeolocate}
      />
    );
    expect(screen.getByPlaceholderText('Enter your starting city…')).toBeInTheDocument();
  });

  it('calls onSubmit with trimmed text on Enter', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <LocationInput placeholder="City…" onSubmit={onSubmit} onGeolocate={onGeolocate} />
    );
    const input = screen.getByPlaceholderText('City…');
    await user.type(input, '  Denver  {Enter}');
    expect(onSubmit).toHaveBeenCalledWith('Denver');
  });

  it('does not call onSubmit when Enter is pressed on an empty field', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <LocationInput placeholder="City…" onSubmit={onSubmit} onGeolocate={onGeolocate} />
    );
    await user.type(screen.getByPlaceholderText('City…'), '{Enter}');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('clears the field after submitting', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <LocationInput placeholder="City…" onSubmit={onSubmit} onGeolocate={onGeolocate} />
    );
    const input = screen.getByPlaceholderText('City…');
    await user.type(input, 'Austin{Enter}');
    expect(input).toHaveValue('');
  });

  it('calls onGeolocate with [lat, lon] when geolocation succeeds', async () => {
    const user = userEvent.setup();

    navigator.geolocation.getCurrentPosition.mockImplementationOnce((success) =>
      success({ coords: { latitude: 39.7392, longitude: -104.9903 } })
    );

    renderWithProviders(
      <LocationInput placeholder="City…" onSubmit={onSubmit} onGeolocate={onGeolocate} />
    );

    await user.click(screen.getByRole('button', { name: /use my location/i }));

    await waitFor(() => {
      expect(onGeolocate).toHaveBeenCalledWith([39.7392, -104.9903]);
    });
  });

  it('renders the geolocation button', () => {
    renderWithProviders(
      <LocationInput placeholder="City…" onSubmit={onSubmit} onGeolocate={onGeolocate} />
    );
    expect(screen.getByRole('button', { name: /use my location/i })).toBeInTheDocument();
  });
});
