/**
 * InputBudget (BudgetSlider) — number field + quick-add buttons tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderWithProviders } from './testUtils';
import BudgetSlider from '../pages/ChatPage/InputBudget';

describe('BudgetSlider', () => {
  const onValueChange = vi.fn();

  beforeEach(() => vi.clearAllMocks());

  const render = (hotelBudget = 0) =>
    renderWithProviders(
      <BudgetSlider
        UserChatData={{ hotelBudget }}
        handleKeyDown={vi.fn()}
        onValueChange={onValueChange}
      />
    );

  it('renders the hotel budget field', () => {
    render();
    expect(screen.getByLabelText(/hotel budget/i)).toBeInTheDocument();
  });

  it('renders quick-add buttons for +$50, +$100, +$500 and Reset', () => {
    render();
    expect(screen.getByRole('button', { name: /^\+\$50$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^\+\$100$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^\+\$500$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('initialises with the minimum hotel budget', () => {
    render(200);
    expect(screen.getByLabelText(/hotel budget/i)).toHaveValue(200);
  });

  it('adds $50 to the current value when +$50 is clicked', async () => {
    const user = userEvent.setup();
    render(100);
    await user.click(screen.getByRole('button', { name: /^\+\$50$/i }));
    // Field should now be 150
    expect(screen.getByLabelText(/hotel budget/i)).toHaveValue(150);
    expect(onValueChange).toHaveBeenCalledWith(150);
  });

  it('resets to minimum on Reset click', async () => {
    const user = userEvent.setup();
    render(100);
    await user.click(screen.getByRole('button', { name: /^\+\$500$/i }));
    await user.click(screen.getByRole('button', { name: /reset/i }));
    expect(screen.getByLabelText(/hotel budget/i)).toHaveValue(100);
  });

  it('clamps typed value below minimum to minimum on blur', async () => {
    const user = userEvent.setup();
    render(200);
    const input = screen.getByLabelText(/hotel budget/i);
    await user.clear(input);
    await user.type(input, '50');
    await user.tab(); // trigger blur
    expect(input).toHaveValue(200); // clamped to minimum
  });
});
