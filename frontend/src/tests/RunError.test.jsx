import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RunError from '../pages/AlgorithmLab/RunError';
import StudioProgress from '../pages/AlgorithmLab/StudioProgress';

it('shows the failed stage and provider cause at the top with saved attempt details', async () => {
  const error = {
    stage: 'candidates',
    code: 'provider_or_planning_failure',
    message: 'AI unavailable',
    http_status: 503,
    causes: [{ type: 'ProviderError', message: 'Gateway returned HTTP 503' }],
  };
  const attempts = [1, 2, 3].map((attempt) => ({
    attempt,
    max_attempts: 3,
    outcome: attempt < 3 ? 'retrying' : 'failed',
  }));
  render(<RunError error={error} attempts={attempts} />);
  expect(screen.getByRole('alert')).toHaveTextContent('candidates: AI unavailable');
  expect(screen.getByText('Gateway returned HTTP 503')).toBeInTheDocument();
  expect(screen.getByText(/2 automatic retries recorded/)).toBeInTheDocument();
  await userEvent.click(screen.getByText('Saved error and attempt details'));
  expect(JSON.parse(screen.getByLabelText('Error diagnostic').textContent)).toEqual({
    error,
    attempts,
  });
});

it('reports a retry in the actual active phase instead of marking the whole run failed', () => {
  render(
    <StudioProgress
      events={[
        {
          type: 'progress',
          stage: 'attractions.ratings',
          state: 'retrying',
          retry: {
            attempt: 1,
            max_attempts: 3,
            outcome: 'retrying',
            causes: [{ message: 'Rate limited' }],
          },
        },
      ]}
    />
  );
  expect(screen.getByRole('status')).toHaveTextContent('Rate limited Retrying: attempt 2 of 3.');
  expect(screen.getByRole('status')).toHaveTextContent('Collect and score nearby places');
  expect(screen.queryByText('Failed')).not.toBeInTheDocument();
});

it('exposes the stored failures when retries recovered and the trip succeeded', () => {
  const attempts = [
    { attempt: 1, outcome: 'retrying', causes: [{ message: 'Gateway temporarily unavailable' }] },
    { attempt: 2, outcome: 'recovered' },
  ];
  render(<RunError error={null} attempts={attempts} />);
  expect(screen.getByText('Saved provider retry details')).toBeInTheDocument();
  expect(screen.getByLabelText('Error diagnostic')).toHaveTextContent(
    'Gateway temporarily unavailable'
  );
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
