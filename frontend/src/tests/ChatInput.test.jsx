import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatInput from '../pages/ChatPage/ChatInput';

describe('creation retry input', () => {
  it('retains text on failure, prevents double sends and clears after retry', async () => {
    let finish;
    const submit = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          })
      )
      .mockResolvedValue(true);
    render(<ChatInput onSubmit={submit} />);
    const input = screen.getByRole('textbox', { name: 'Chat message' });
    await userEvent.type(input, 'Boulder');
    await userEvent.dblClick(screen.getByRole('button', { name: 'Send message' }));
    expect(submit).toHaveBeenCalledTimes(1);
    finish(false);
    await waitFor(() => expect(input).toHaveValue('Boulder'));
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(() => expect(input).toHaveValue(''));
    expect(submit).toHaveBeenCalledTimes(2);
  });
});
