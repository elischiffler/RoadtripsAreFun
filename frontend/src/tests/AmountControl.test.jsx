import { useState } from 'react';
import PropTypes from 'prop-types';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { AmountControl, DesignFrame } from '../design';

function ControlledAmount({ initial = 0.123456789, initialMax = 1, disabled = false, onSubmit }) {
  const [amount, setAmount] = useState(initial);
  return (
    <DesignFrame>
      <form onSubmit={onSubmit}>
        <AmountControl
          label="Food"
          value={amount}
          onChange={setAmount}
          initialMax={initialMax}
          disabled={disabled}
        />
        <span data-testid="exact-amount">{String(amount)}</span>
      </form>
    </DesignFrame>
  );
}
ControlledAmount.propTypes = {
  initial: PropTypes.number,
  initialMax: PropTypes.number,
  disabled: PropTypes.bool,
  onSubmit: PropTypes.func,
};

it('uses a labeled native continuous slider and leaves precise stored values untouched on render', async () => {
  const changed = vi.fn();
  const view = render(
    <AmountControl label="Food" value={0.123456789} onChange={changed} initialMax={1} />
  );
  const slider = screen.getByRole('slider', { name: 'Food' });
  expect(slider).toHaveAttribute('step', 'any');
  expect(slider).toHaveAttribute('min', '0');
  expect(slider).toHaveAttribute('aria-valuetext', '0.123456789 relative amount');
  expect(Number(slider.value)).toBe(0.123456789);
  view.rerender(
    <AmountControl label="Food" value={123456.789123} onChange={changed} initialMax={1} />
  );
  expect(Number(slider.value)).toBe(123456.789123);
  expect(Number(slider.max)).toBeGreaterThanOrEqual(123456.789123);
  expect(changed).not.toHaveBeenCalled();
});

it('adjusts by taps and continuous changes, clamps at zero, and never submits its form', async () => {
  const submit = vi.fn((event) => event.preventDefault());
  render(<ControlledAmount initial={0.005} onSubmit={submit} />);
  await userEvent.click(screen.getByRole('button', { name: 'Less Food' }));
  expect(screen.getByTestId('exact-amount')).toHaveTextContent('0');
  expect(screen.getByRole('button', { name: 'Less Food' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'More Food' }));
  expect(Number(screen.getByRole('slider', { name: 'Food' }).value)).toBeGreaterThan(0);
  const maximum = screen.getByRole('slider', { name: 'Food' }).max;
  fireEvent.change(screen.getByRole('slider', { name: 'Food' }), {
    target: { value: '0.987654321' },
  });
  expect(screen.getByTestId('exact-amount')).toHaveTextContent('0.987654321');
  fireEvent.change(screen.getByRole('slider', { name: 'Food' }), { target: { value: '0.25' } });
  expect(screen.getByRole('slider', { name: 'Food' }).max).toBe(maximum);
  expect(submit).not.toHaveBeenCalled();
});

it('keeps very large finite amounts usable and honors disabled controls', async () => {
  const view = render(<ControlledAmount initial={1e200} initialMax={1e200} />);
  await userEvent.click(screen.getByRole('button', { name: 'More Food' }));
  expect(Number(screen.getByRole('slider', { name: 'Food' }).value)).toBeGreaterThan(1e200);
  view.unmount();
  render(<ControlledAmount initial={Number.MAX_VALUE} initialMax={Number.MAX_VALUE} disabled />);
  expect(screen.getByRole('slider', { name: 'Food' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'More Food' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Less Food' })).toBeDisabled();
});

it('announces tap adjustments while keeping button focus and leaves slider feedback to the native control', async () => {
  render(<ControlledAmount initial={0.25} />);
  const more = screen.getByRole('button', { name: 'More Food' });
  await userEvent.click(more);
  expect(more).toHaveFocus();
  expect(screen.getByRole('status')).toHaveTextContent('Food: 0.26 relative amount');
  fireEvent.change(screen.getByRole('slider', { name: 'Food' }), { target: { value: '0.5' } });
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  expect(screen.getByRole('slider', { name: 'Food' })).toHaveAttribute(
    'aria-valuetext',
    '0.5 relative amount'
  );
});
