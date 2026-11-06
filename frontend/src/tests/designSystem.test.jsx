import { useState } from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  ActionButton,
  ChoiceGroup,
  DesignFrame,
  Field,
  QuestionGroup,
  Sheet,
  StageProgress,
  TripTimeline,
  TripViewSwitch,
} from '../design';
import DesignSystemExample from '../design/DesignSystemExample';

function Choices() {
  const [value, setValue] = useState('slow');
  return (
    <ChoiceGroup
      legend="Trip pace"
      value={value}
      onChange={setValue}
      options={[
        { value: 'slow', label: 'Take it slow' },
        { value: 'busy', label: 'Fit more in' },
        { value: 'closed', label: 'Unavailable', disabled: true },
      ]}
    />
  );
}
function Views() {
  const [value, setValue] = useState('itinerary');
  return <TripViewSwitch value={value} onChange={setValue} />;
}

describe('mobile design primitives', () => {
  it('groups questions and connects input labels, hints, errors and caller descriptions', () => {
    render(
      <DesignFrame>
        <Sheet aria-label="Trip details">
          <p id="external">Locations need confirmation.</p>
          <QuestionGroup legend="Your route" description="Start with the essentials.">
            <Field
              label="Starting city"
              hint="Enter a city."
              error="Choose a location."
              aria-describedby="external"
              defaultValue="Denver"
            />
          </QuestionGroup>
        </Sheet>
      </DesignFrame>
    );
    expect(screen.getByRole('region', { name: 'Trip details' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Your route' })).toHaveAccessibleDescription(
      'Start with the essentials.'
    );
    const input = screen.getByRole('textbox', { name: 'Starting city' });
    expect(input).toHaveAccessibleDescription(
      'Locations need confirmation. Enter a city. Choose a location.'
    );
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });
  it('creates unique input IDs and removes stale invalid state when an error clears', () => {
    const { rerender } = render(
      <>
        <Field label="First city" error="Required" />
        <Field label="Second city" hint="Optional" />
      </>
    );
    expect(screen.getByLabelText('First city').id).not.toBe(
      screen.getByLabelText('Second city').id
    );
    rerender(<Field label="First city" hint="Ready" />);
    expect(screen.getByLabelText('First city')).not.toHaveAttribute('aria-invalid');
    expect(screen.getByLabelText('First city')).toHaveAccessibleDescription('Ready');
  });
  it('uses native radio keyboard selection and respects disabled options', async () => {
    const user = userEvent.setup();
    render(<Choices />);
    const slow = screen.getByRole('radio', { name: 'Take it slow' });
    await user.tab();
    expect(slow).toHaveFocus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('radio', { name: 'Fit more in' })).toBeChecked();
    expect(slow).not.toBeChecked();
    expect(screen.getByRole('radio', { name: 'Unavailable' })).toBeDisabled();
    await user.click(screen.getByText('Unavailable'));
    expect(screen.getByRole('radio', { name: 'Fit more in' })).toBeChecked();
  });
  it('defaults actions to non-submitting buttons and allows keyboard activation', async () => {
    const action = vi.fn();
    const submit = vi.fn((event) => event.preventDefault());
    const user = userEvent.setup();
    render(
      <form onSubmit={submit}>
        <ActionButton onClick={action}>Continue</ActionButton>
        <ActionButton disabled>Wait</ActionButton>
      </form>
    );
    await user.tab();
    await user.keyboard('{Enter}');
    expect(action).toHaveBeenCalledOnce();
    expect(submit).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Wait' }));
    expect(action).toHaveBeenCalledOnce();
  });
  it('reports actual unique completed stages and marks the current stage', () => {
    render(
      <StageProgress
        stages={[
          { id: 'route', label: 'Route' },
          { id: 'people', label: 'Travelers' },
          { id: 'review', label: 'Review' },
        ]}
        currentId="people"
        completedIds={['route', 'route', 'unknown']}
      />
    );
    const progress = screen.getByRole('progressbar');
    expect(progress).toHaveAccessibleName('1 of 3 stages complete');
    expect(progress).toHaveAttribute('value', '1');
    expect(progress).toHaveAttribute('max', '3');
    expect(screen.getByText('2. Travelers')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByText('1. Route · Complete')).not.toHaveAttribute('aria-current');
  });
  it('labels timeline states with text and keeps machine-readable times', () => {
    render(
      <TripTimeline
        label="Day one"
        items={[
          {
            id: 'a',
            title: 'Leave Denver',
            time: '9 AM',
            dateTime: '2027-06-14T09:00',
            status: 'complete',
          },
          { id: 'b', title: 'Coffee stop', time: '10 AM', status: 'current' },
          { id: 'c', title: 'Lunch', time: 'Noon' },
        ]}
      />
    );
    const items = within(screen.getByRole('list', { name: 'Day one' })).getAllByRole('listitem');
    expect(within(items[0]).getByText('Visited')).toBeInTheDocument();
    expect(within(items[0]).getByText('9 AM')).toHaveAttribute('datetime', '2027-06-14T09:00');
    expect(items[1]).toHaveAttribute('aria-current', 'step');
    expect(within(items[1]).getByText('Current stop')).toBeInTheDocument();
    expect(within(items[2]).getByText('Upcoming')).toBeInTheDocument();
  });
  it('switches views with native selection semantics', async () => {
    const user = userEvent.setup();
    render(<Views />);
    expect(screen.getByRole('radio', { name: 'Itinerary' })).toBeChecked();
    await user.click(screen.getByRole('radio', { name: 'Map' }));
    expect(screen.getByRole('radio', { name: 'Map' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Itinerary' })).not.toBeChecked();
  });
  it('composes every public primitive without services or routing', async () => {
    const user = userEvent.setup();
    render(<DesignSystemExample />);
    expect(screen.getByRole('list', { name: 'Monday itinerary example' })).toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: 'Map' }));
    expect(
      screen.queryByRole('list', { name: 'Monday itinerary example' })
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Back to itinerary' }));
    expect(screen.getByRole('list', { name: 'Monday itinerary example' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save example choices' }));
    expect(screen.getByRole('status')).toHaveTextContent('Example choices saved for this preview.');
  });
});
