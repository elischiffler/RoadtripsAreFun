import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import BenchmarkDialog from '../pages/AlgorithmLab/BenchmarkDialog';
import { runLab } from '../services/algorithmLab';

vi.mock('../services/algorithmLab', () => ({
  runLab: vi.fn(),
  labError: () => 'Storage unavailable',
}));
const catalog = {
  benchmarks: [
    { id: 'short', label: 'Short', description: 'Two stops', inputs: { num_stops: 2 } },
    { id: 'long', label: 'Long', description: 'Eight stops', inputs: { num_stops: 8 } },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});
afterEach(() => vi.restoreAllMocks());
function open() {
  const onResult = vi.fn();
  render(
    <BenchmarkDialog catalog={catalog} disabled={false} onBusy={vi.fn()} onResult={onResult} />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Benchmark trips' }));
  fireEvent.click(screen.getByLabelText(/Short/));
  fireEvent.click(screen.getByLabelText(/Long/));
  return onResult;
}
it('waits for each recorded run before starting the next and shares a batch ID', async () => {
  let finish;
  runLab.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  runLab.mockResolvedValue({ run_record: { saved: true } });
  const onResult = open();
  fireEvent.click(screen.getByRole('button', { name: 'Run 2 experiments sequentially' }));
  expect(runLab).toHaveBeenCalledTimes(1);
  await act(async () => finish({ run_record: { saved: true } }));
  await waitFor(() => expect(onResult).toHaveBeenCalledTimes(2));
  expect(runLab.mock.calls[0][0].batch_id).toBe(runLab.mock.calls[1][0].batch_id);
  expect(runLab.mock.calls[1][0].preset_id).toBe('long');
});
it('stops future runs while allowing the current result to be saved', async () => {
  let finish;
  runLab.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Run 2 experiments sequentially' }));
  fireEvent.click(screen.getByRole('button', { name: 'Stop after current run' }));
  await act(async () => finish({ run_record: { saved: true } }));
  expect(runLab).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/remaining runs stopped/)).toBeInTheDocument();
});
it('halts a queue when persistence cannot be confirmed', async () => {
  runLab.mockResolvedValue({ run_record: { saved: false } });
  open();
  fireEvent.click(screen.getByRole('button', { name: 'Run 2 experiments sequentially' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Result storage failed');
  expect(runLab).toHaveBeenCalledTimes(1);
});
