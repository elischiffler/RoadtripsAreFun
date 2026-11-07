import { useState } from 'react';
import { expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DailyRhythm from '../pages/TripSetup/DailyRhythm.jsx';
import { dailyScheduleFromRhythm, schedulingPolicyFromDraft } from '../pages/TripSetup/dailyRhythm';
import { newSetupDraft, setupErrors } from '../pages/TripSetup/setupModel';
import { applyPreferenceChoices, choicesFromDraft } from '../services/preferenceProfiles';
const night = { driveStart: 20, driveEnd: 6, sleepStart: 8, sleepEnd: 16 };

it('labels midnight crossings without restricting night driving or daytime sleep', () => {
  const change = vi.fn();
  render(<DailyRhythm value={night} onChange={change} />);
  expect(screen.getByRole('slider', { name: 'Stop driving' })).toHaveAttribute(
    'aria-valuetext',
    '06:00, next day'
  );
  expect(screen.getByRole('slider', { name: 'Wake up' })).toHaveAttribute(
    'aria-valuetext',
    '16:00'
  );
  expect(screen.getByRole('img')).toHaveAccessibleName(
    'Drive 20:00 to 06:00, next day; sleep 08:00 to 16:00. Other hours are rest.'
  );
  expect(screen.getByText('+1 day')).toBeInTheDocument();
  expect(screen.queryByText(/unsupported|one-day only/i)).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
  expect(screen.getByText(/Meals follow sleep/)).toBeInTheDocument();
  for (const slider of screen.getAllByRole('slider')) expect(slider).toBeEnabled();
});
it('tracks each changed hour directly and keeps overlap errors actionable', async () => {
  function Editor() {
    const [value, setValue] = useState(night);
    return <DailyRhythm value={value} onChange={setValue} />;
  }
  render(<Editor />);
  fireEvent.change(screen.getByRole('slider', { name: 'Stop driving' }), {
    target: { value: '0' },
  });
  expect(screen.getByRole('slider', { name: 'Stop driving' })).toHaveAttribute(
    'aria-valuetext',
    '00:00, next day'
  );
  fireEvent.change(screen.getByRole('slider', { name: 'Start sleep' }), {
    target: { value: '23' },
  });
  expect(screen.getByRole('status')).toHaveTextContent('Driving and sleep hours overlap');
  expect(screen.getByRole('slider', { name: 'Start sleep' })).toBeEnabled();
  fireEvent.change(screen.getByRole('slider', { name: 'Start sleep' }), { target: { value: '8' } });
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  await userEvent.tab();
  expect(screen.getByRole('slider', { name: 'Start driving' })).toHaveFocus();
});
it('keeps valid night policies through reusable profiles and structured validation without legacy clock overrides', () => {
  const draft = { ...newSetupDraft(), dailyRhythm: night, date: '2027-06-01', time: '20:00' };
  expect(setupErrors(draft, 3)).toEqual({});
  expect(Object.keys(schedulingPolicyFromDraft(draft))).toEqual(['daily_schedule']);
  const policy = dailyScheduleFromRhythm(night);
  expect(policy.slots.slice(0, 6)).toEqual(Array(6).fill('drive'));
  expect(policy.slots.slice(8, 16)).toEqual(Array(8).fill('sleep'));
  const choices = choicesFromDraft(draft);
  const restored = applyPreferenceChoices(newSetupDraft(), choices);
  expect(restored.dailyRhythm).toEqual(night);
  expect(schedulingPolicyFromDraft(restored)).toEqual({ daily_schedule: policy });
  expect(setupErrors({ ...draft, time: '12:00' }, 3).schedule).toMatch(
    /Departure is outside driving hours/
  );
});
it('leaves saved legacy timing untouched until explicit conversion', async () => {
  const change = vi.fn();
  render(<DailyRhythm value={null} onChange={change} />);
  expect(screen.getByText(/Existing timing stays in use/)).toBeInTheDocument();
  expect(screen.queryByText(/Meals follow sleep/)).not.toBeInTheDocument();
  expect(change).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Use this rhythm' }));
  expect(change).toHaveBeenCalledTimes(1);
});
