/**
 * InputCar (CarInputBar) — three-field car details input tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderWithProviders } from './testUtils';
import CarInputBar from '../pages/ChatPage/InputCar';

describe('CarInputBar', () => {
  const onValueChange = vi.fn();
  const handleKeyDown = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  it('renders Year, Make, and Model fields', () => {
    renderWithProviders(
      <CarInputBar onValueChange={onValueChange} handleKeyDown={handleKeyDown} />
    );
    expect(screen.getByPlaceholderText('Year')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Make')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Model')).toBeInTheDocument();
  });

  it('calls onValueChange with [year, make, model] as user types', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <CarInputBar onValueChange={onValueChange} handleKeyDown={handleKeyDown} />
    );

    await user.type(screen.getByPlaceholderText('Year'), '2020');
    await user.type(screen.getByPlaceholderText('Make'), 'Toyota');
    await user.type(screen.getByPlaceholderText('Model'), 'Camry');

    // Last call should have all three fields filled
    const lastCall = onValueChange.mock.calls.at(-1)[0];
    expect(lastCall[0]).toBe('2020');
    expect(lastCall[1]).toBe('Toyota');
    expect(lastCall[2]).toBe('Camry');
  });

  it('starts with all fields empty', () => {
    renderWithProviders(
      <CarInputBar onValueChange={onValueChange} handleKeyDown={handleKeyDown} />
    );
    expect(screen.getByPlaceholderText('Year')).toHaveValue('');
    expect(screen.getByPlaceholderText('Make')).toHaveValue('');
    expect(screen.getByPlaceholderText('Model')).toHaveValue('');
  });
});
