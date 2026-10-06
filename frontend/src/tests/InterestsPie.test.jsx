import { useState } from 'react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import InterestsPie from '../pages/AlgorithmLab/InterestsPie';
const attributes = ['nature', 'history', 'food'];
function mount(initial = { nature: 0.5, history: 0.25, food: 0 }, disabled = false) {
  const changed = vi.fn();
  function Harness() {
    const [weights, setWeights] = useState(initial);
    return (
      <InterestsPie
        attributes={attributes}
        weights={weights}
        disabled={disabled}
        onChange={(next) => {
          changed(next);
          setWeights(next);
        }}
      />
    );
  }
  render(<Harness />);
  return changed;
}
const value = (name) => screen.getByLabelText(`Interest ${name} percentage`);
const handle = (name) => screen.getByRole('slider', { name: `Resize ${name}` });
const position = (share) => ({
  clientX: 140 + 110 * Math.sin(share * Math.PI * 2),
  clientY: 140 - 110 * Math.cos(share * Math.PI * 2),
});
beforeEach(() => {
  vi.stubGlobal(
    'PointerEvent',
    class extends MouseEvent {
      constructor(type, props) {
        super(type, props);
        this.pointerId = props.pointerId ?? 1;
        this.pointerType = props.pointerType ?? 'mouse';
      }
    }
  );
  Element.prototype.setPointerCapture = vi.fn();
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 280,
    height: 280,
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
});
describe('trip-interest pie interactions', () => {
  it('shows a drop overlay and adds only on drop; cancelled and unrelated drops do nothing', () => {
    const changed = mount();
    const chip = screen.getByRole('button', { name: 'Add food' });
    fireEvent.pointerDown(chip, { button: 0, clientX: 140, clientY: 340 });
    expect(screen.getByText('Drop food here')).toBeInTheDocument();
    fireEvent.pointerCancel(chip);
    fireEvent.pointerUp(chip, { clientX: 140, clientY: 140 });
    expect(changed).not.toHaveBeenCalled();
    fireEvent.pointerDown(chip, { button: 0, clientX: 140, clientY: 340 });
    fireEvent.pointerMove(chip, { clientX: 140, clientY: 140 });
    fireEvent.pointerUp(chip, { clientX: 140, clientY: 140 });
    expect(value('food')).toHaveValue(10);
    expect(screen.queryByText('Drop food here')).not.toBeInTheDocument();
    expect(changed).toHaveBeenLastCalledWith({ nature: 0.5, history: 0.25, food: 0.1 });
  });
  it('caps edits and drops at available capacity without altering other topics', () => {
    const changed = mount();
    fireEvent.change(value('nature'), { target: { value: '999' } });
    expect(value('nature')).toHaveValue(75);
    expect(changed).toHaveBeenLastCalledWith({ nature: 0.75, history: 0.25, food: 0 });
    fireEvent.click(screen.getByRole('button', { name: 'Add food' }));
    expect(screen.getByRole('status')).toHaveTextContent('Free at least 1%');
    expect(screen.queryByLabelText('Interest food percentage')).not.toBeInTheDocument();
    fireEvent.change(value('nature'), { target: { value: '74.8' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add food' }));
    expect(screen.queryByLabelText('Interest food percentage')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Free at least 1%');
    fireEvent.change(value('nature'), { target: { value: '74' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add food' }));
    expect(value('food')).toHaveValue(1);
    expect(
      Object.values(changed.mock.lastCall[0]).reduce((sum, item) => sum + item, 0)
    ).toBeCloseTo(1, 12);
  });
  it('resizes by dragging an edge and stops on release', () => {
    const changed = mount();
    const edge = handle('nature');
    fireEvent.pointerDown(edge, { button: 0, ...position(0.5) });
    fireEvent.pointerMove(edge, position(0.625));
    expect(value('nature')).toHaveValue(62.5);
    expect(value('history')).toHaveValue(25);
    fireEvent.pointerUp(edge);
    const calls = changed.mock.calls.length;
    fireEvent.pointerMove(edge, position(0.75));
    expect(changed).toHaveBeenCalledTimes(calls);
  });
  it('stops pointer resizing at 1% without removing the topic', () => {
    mount({ nature: 0.02, history: 0.25, food: 0 });
    const edge = handle('nature');
    fireEvent.pointerDown(edge, { button: 0, ...position(0.02) });
    fireEvent.pointerMove(edge, position(0.99));
    expect(value('nature')).toHaveValue(1);
    expect(handle('nature')).toHaveAttribute('aria-valuemin', '1');
    expect(value('history')).toHaveValue(25);
  });
  it('unwraps the top seam without a 100% jump, caps at 100%, and cancels cleanly', () => {
    mount({ nature: 0.95, history: 0, food: 0 });
    const edge = handle('nature');
    fireEvent.pointerDown(edge, { button: 0, ...position(0.95) });
    fireEvent.pointerMove(edge, position(0.99));
    expect(value('nature')).toHaveValue(99);
    fireEvent.pointerMove(edge, position(0.01));
    expect(value('nature')).toHaveValue(100);
    fireEvent.pointerCancel(edge);
    expect(handle('nature')).not.toHaveClass('is-resizing');
  });
  it('keeps the field mounted while typing but clamps sub-percent and zero values to 1%', () => {
    mount();
    fireEvent.change(value('nature'), { target: { value: '' } });
    expect(value('nature')).toHaveValue(null);
    fireEvent.change(value('nature'), { target: { value: '0' } });
    fireEvent.change(value('nature'), { target: { value: '0.5' } });
    expect(value('nature')).toHaveValue(1);
    fireEvent.change(value('nature'), { target: { value: '0' } });
    fireEvent.blur(value('nature'));
    expect(value('nature')).toHaveValue(1);
  });
  it('supports keyboard resize, removal and click-to-add from an empty circle', () => {
    mount();
    fireEvent.keyDown(handle('nature'), { key: 'ArrowDown', shiftKey: true });
    expect(value('nature')).toHaveValue(45);
    fireEvent.keyDown(handle('nature'), { key: 'End' });
    expect(value('nature')).toHaveValue(75);
    fireEvent.keyDown(handle('nature'), { key: 'Home' });
    expect(value('nature')).toHaveValue(1);
    fireEvent.keyDown(handle('nature'), { key: 'ArrowDown' });
    expect(value('nature')).toHaveValue(1);
    fireEvent.click(screen.getByRole('button', { name: 'Remove nature' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove history' }));
    expect(screen.getByText('Add at least one topic to run.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Add food' }));
    expect(value('food')).toHaveValue(10);
  });
  it('supports touch drag into the circle', () => {
    const changed = mount();
    const chip = screen.getByRole('button', { name: 'Add food' });
    fireEvent.pointerDown(chip, { pointerType: 'touch', clientX: 140, clientY: 340 });
    fireEvent.pointerMove(chip, { pointerType: 'touch', clientX: 140, clientY: 140 });
    fireEvent.pointerUp(chip, { pointerType: 'touch', clientX: 140, clientY: 140 });
    expect(changed).toHaveBeenCalledTimes(1);
    expect(value('food')).toHaveValue(10);
  });
  it('disables mutation during a run and renders equivalent shares for relative presets', () => {
    const changed = mount({ nature: 2, history: 1, food: 0 }, true);
    expect(value('nature')).toHaveValue(66.7);
    expect(handle('nature')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Add food' }));
    fireEvent.pointerDown(handle('nature'), { button: 0, ...position(0.5) });
    fireEvent.pointerMove(handle('nature'), position(0.6));
    expect(changed).not.toHaveBeenCalled();
  });
});
