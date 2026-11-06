import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import TripSetup from '../pages/TripSetup/TripSetup';
import {
  COMPARISONS,
  INTERESTS,
  newSetupDraft,
  preferenceProfiles,
  preferenceWeights,
} from '../pages/TripSetup/setupModel';
import { SETUP_DRAFT_PREFIX } from '../pages/TripSetup/useSetupDraft';
import { getSession, signOut } from '../services/session';

const key = () => SETUP_DRAFT_PREFIX + encodeURIComponent(getSession().owner);
const fill = (name, value) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
function seed(draft, step) {
  sessionStorage.setItem(key(), JSON.stringify({ version: 1, draft, step }));
}
const validDraft = () => ({
  ...newSetupDraft(),
  start: 'Boulder',
  destination: 'Denver',
  date: '2027-06-01',
  carStatus: 'skipped',
});
beforeEach(() => {
  sessionStorage.clear();
  fixtureSession('setup-owner');
});

describe('accessible trip setup', () => {
  it('keeps answers across Back, completed step edits and reload; focuses inline errors', async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    const view = renderWithProviders(<TripSetup onSubmit={submit} />);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('alert')).toHaveFocus();
    expect(screen.getByLabelText('Starting city or address')).toHaveAttribute(
      'aria-invalid',
      'true'
    );
    fill('Starting city or address', 'Boulder');
    fill('Destination', 'Denver');
    fill('Departure date', '2027-06-01');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('heading', { name: 'People and rooms' })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('heading', { name: 'What you enjoy' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.click(screen.getByRole('button', { name: /Step 1:/ }));
    expect(screen.getByLabelText('Starting city or address')).toHaveValue('Boulder');
    await user.click(screen.getByRole('button', { name: /Step 3:/ }));
    view.unmount();
    renderWithProviders(<TripSetup onSubmit={submit} />);
    expect(screen.getByRole('heading', { name: 'What you enjoy' })).toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
  });
  it('compares one pair at a time, preserves manual interests and supports every choice/reset/skip', async () => {
    const draft = {
      ...validDraft(),
      customWeights: Object.fromEntries(
        Object.keys(INTERESTS).map((key) => [key, key === 'food' ? 10 : 1])
      ),
    };
    seed(draft, 2);
    const user = userEvent.setup();
    renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
    const pair = COMPARISONS[0];
    const stored = () => JSON.parse(sessionStorage.getItem(key())).draft;
    expect(screen.getAllByRole('article')).toHaveLength(2);
    expect(screen.getByRole('heading', { name: pair.left.name })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: pair.right.name })).toBeInTheDocument();
    const leftPlace = screen.getByRole('heading', { name: pair.left.name }).closest('article');
    await user.click(within(leftPlace).getByText('Place source'));
    expect(within(leftPlace).getByRole('link')).toHaveAttribute('href', pair.left.url);
    for (const [choice, label] of [
      ['left', pair.left.name],
      ['right', pair.right.name],
      ['either', 'Either place'],
      ['neither', 'Neither place'],
      ['unsure', 'Not sure'],
    ]) {
      await user.click(screen.getByRole('radio', { name: label, exact: true }));
      expect(stored().comparisonAnswers[pair.id]).toBe(choice);
      expect(stored().customWeights).toEqual(draft.customWeights);
    }
    expect(preferenceWeights(stored())).toEqual(preferenceProfiles(stored()).stated);
    await user.click(screen.getByRole('radio', { name: pair.left.name, exact: true }));
    await user.click(screen.getByRole('button', { name: 'Next comparison' }));
    expect(screen.getByRole('heading', { name: COMPARISONS[1].left.name })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Previous comparison' }));
    expect(screen.getByRole('radio', { name: pair.left.name, exact: true })).toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Reset comparisons' }));
    expect(stored().comparisonAnswers).toEqual({});
    expect(stored().customWeights).toEqual(draft.customWeights);
    await user.click(screen.getByRole('button', { name: 'Skip this comparison' }));
    expect(stored().comparisonAnswers[pair.id]).toBe('unsure');
    await user.click(screen.getByRole('checkbox', { name: 'Food', exact: true }));
    await user.click(screen.getByRole('button', { name: 'Reset interests' }));
    expect(screen.getByRole('checkbox', { name: 'Food', exact: true })).not.toBeChecked();
    expect(stored().comparisonAnswers[pair.id]).toBe('unsure');
    expect(screen.queryByRole('figure')).not.toBeInTheDocument();
    expect(
      screen.queryByText(/50\/50|inferred|personality|combined profile/i)
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Skip interests and use a balanced mix' }));
    expect(stored().comparisonAnswers).toEqual({});
    expect(screen.getByRole('heading', { name: 'Car and timing' })).toBeInTheDocument();
  });
  it('renders the route estimate after location inputs without submitting answers', () => {
    const submit = vi.fn();
    const estimate = vi.fn((draft) => <p>Estimate for {draft.start || 'your route'}</p>);
    renderWithProviders(<TripSetup onSubmit={submit} renderEstimate={estimate} />);
    fill('Starting city or address', 'Boulder');
    expect(estimate).toHaveBeenLastCalledWith(expect.objectContaining({ start: 'Boulder' }));
    expect(screen.getByText('Estimate for Boulder')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Studio/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Saved trips' })).toHaveAttribute('href', '/trips');
    expect(submit).not.toHaveBeenCalled();
  });
  it('keeps manual editing and review limited to stated interests', async () => {
    const draft = {
      ...validDraft(),
      interests: ['food'],
      comparisonAnswers: { [COMPARISONS[0].id]: 'left' },
    };
    seed(draft, 2);
    renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit interest amounts'));
    const details = screen.getByText('Edit interest amounts').closest('details');
    expect(within(details).getByLabelText('Food')).toHaveValue(
      Number((preferenceProfiles(draft).stated.food * 100).toFixed(3))
    );
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    const review = screen.getByRole('heading', { name: 'What you enjoy' }).closest('section');
    expect(within(review).getByText('Food')).toBeInTheDocument();
    expect(screen.queryByRole('figure')).not.toBeInTheDocument();
  });
  it('validates rooms, supports car/timing inputs and requires explicit final submission', async () => {
    seed(validDraft(), 1);
    const user = userEvent.setup(),
      submit = vi.fn();
    renderWithProviders(<TripSetup onSubmit={submit} />);
    await user.click(screen.getByRole('button', { name: 'Add a room' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Room occupants must add up');
    await user.click(screen.getByRole('button', { name: 'Remove room 2' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Skip interests and use a balanced mix' }));
    const carLabel = screen.getByText('Would you like to add your car?', { exact: true });
    expect(carLabel).toHaveAttribute('for', 'setup-carStatus');
    expect(carLabel.textContent).toBe('Would you like to add your car?');
    expect(carLabel).not.toContainElement(screen.getByRole('combobox'));
    await user.selectOptions(
      screen.getByLabelText('Would you like to add your car?', { exact: true }),
      'provided'
    );
    fill('Car year', '2020');
    fill('Car make', 'Toyota');
    fill('Car model', 'Corolla');
    await user.click(screen.getByLabelText('Allow driving later into the evening'));
    expect(screen.getByLabelText(/Stop late driving by/)).toHaveValue('24:00');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('heading', { name: 'Review', exact: true })).toHaveFocus();
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Edit People and rooms' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Reset draft', exact: true }));
    await user.click(screen.getByRole('button', { name: 'Keep answers' }));
    expect(screen.getByRole('heading', { name: 'Review', exact: true })).toBeInTheDocument();
  });
  it('passes structured answers to address confirmation without generating a message', async () => {
    const draft = { ...validDraft(), interests: ['food'] };
    seed(draft, 4);
    const submit = vi.fn().mockResolvedValue({ ok: true });
    renderWithProviders(<TripSetup onSubmit={submit} />);
    await userEvent.click(screen.getByRole('button', { name: 'Check locations' }));
    expect(submit).toHaveBeenCalledWith({ draft });
    expect(submit.mock.calls[0][0]).not.toHaveProperty('message');
    expect(screen.queryByText(/Continue in chat/)).not.toBeInTheDocument();
  });
  it('keeps address validation errors and draft answers', async () => {
    seed(validDraft(), 4);
    renderWithProviders(
      <TripSetup onSubmit={vi.fn().mockResolvedValue({ error: 'Location not found' })} />
    );
    await userEvent.click(screen.getByRole('button', { name: 'Check locations' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Location not found');
    expect(sessionStorage.getItem(key())).not.toBeNull();
  });
  it('keeps the draft on a network failure, resets explicitly and removes account data on sign out', async () => {
    seed(validDraft(), 4);
    renderWithProviders(<TripSetup onSubmit={vi.fn().mockRejectedValue(new Error('offline'))} />);
    await userEvent.click(screen.getByRole('button', { name: 'Check locations' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Your draft is kept');
    await userEvent.click(screen.getByRole('button', { name: 'Reset draft', exact: true }));
    await userEvent.click(screen.getByRole('button', { name: 'Clear draft answers' }));
    expect(screen.getByLabelText('Starting city or address')).toHaveValue('');
    const oldKey = key();
    signOut();
    await waitFor(() => expect(sessionStorage.getItem(oldKey)).toBeNull());
  });
  it('does not cross owners or accept corrupted drafts', () => {
    sessionStorage.setItem(key(), 'broken');
    const view = renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
    expect(screen.getByLabelText('Starting city or address')).toHaveValue('');
    fill('Starting city or address', 'Private draft');
    act(() => fixtureSession('another-owner'));
    expect(screen.getByLabelText('Starting city or address')).toHaveValue('');
    view.unmount();
    renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
    expect(screen.getByLabelText('Starting city or address')).toHaveValue('');
  });
  it('prevents an all-zero manually edited profile from progressing', async () => {
    seed(validDraft(), 2);
    renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit interest amounts'));
    const details = screen.getByText('Edit interest amounts').closest('details');
    for (const label of Object.values(INTERESTS))
      fireEvent.change(within(details).getByLabelText(label), { target: { value: '0' } });
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('alert')).toHaveTextContent('above zero');
  });
});
