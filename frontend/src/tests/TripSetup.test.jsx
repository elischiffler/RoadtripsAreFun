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

vi.mock('../services/preferenceProfiles', async (original) => ({
  ...(await original()),
  loadPreferenceProfiles: vi.fn(async () => []),
  saveNewTripPreferences: vi.fn(async () => undefined),
}));
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
    expect(screen.getByRole('progressbar', { name: 'Trip setup completion' })).toHaveAttribute(
      'value',
      '0'
    );
    expect(screen.queryByRole('button', { name: /Step 1:/ })).not.toBeInTheDocument();
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
    expect(screen.getByRole('heading', { name: 'People' })).toHaveFocus();
    expect(screen.getByRole('progressbar', { name: 'Trip setup completion' })).toHaveAttribute(
      'value',
      '25'
    );
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('heading', { name: 'What you enjoy' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Back' }));
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByLabelText('Starting city or address')).toHaveValue('Boulder');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
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
    await user.click(screen.getByText('Compare places'));
    const pair = COMPARISONS[0];
    const stored = () => JSON.parse(sessionStorage.getItem(key())).draft;
    expect(screen.getAllByRole('article')).toHaveLength(2);
    expect(screen.getByRole('heading', { name: pair.left.name })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: pair.right.name })).toBeInTheDocument();
    const leftPlace = screen.getByRole('heading', { name: pair.left.name }).closest('article');
    expect(within(leftPlace).queryByText('Place source')).not.toBeInTheDocument();
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
    expect(screen.queryByRole('checkbox', { name: 'Food', exact: true })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Done adjusting interests' }));
    expect(screen.getByText('Compare places')).toHaveFocus();
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
    expect(screen.getByRole('heading', { name: 'Daily timing' })).toBeInTheDocument();
  });
  it('renders the route estimate after location inputs without submitting answers', () => {
    const submit = vi.fn();
    const estimate = vi.fn((draft) => <p>Estimate for {draft.start || 'your route'}</p>);
    renderWithProviders(<TripSetup onSubmit={submit} renderEstimate={estimate} />);
    fill('Starting city or address', 'Boulder');
    expect(estimate).toHaveBeenLastCalledWith(expect.objectContaining({ start: 'Boulder' }), 0);
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
    await userEvent.click(screen.getByText('Adjust amounts'));
    const details = screen.getByText('Adjust amounts').closest('details');
    expect(Number(within(details).getByRole('slider', { name: 'Food' }).value)).toBe(
      preferenceProfiles(draft).stated.food * 100
    );
    await userEvent.click(screen.getByRole('button', { name: 'Done adjusting interests' }));
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    const review = screen.getByRole('heading', { name: 'What you enjoy' }).closest('section');
    expect(within(review).getByText('Food')).toBeInTheDocument();
    expect(screen.queryByRole('figure')).not.toBeInTheDocument();
  });
  it('validates rooms, keeps car in settings and supports timing and requires explicit final submission', async () => {
    seed(validDraft(), 1);
    const user = userEvent.setup(),
      submit = vi.fn();
    renderWithProviders(<TripSetup onSubmit={submit} />);
    expect(screen.queryByRole('button', { name: 'Add a room' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Skip interests and use a balanced mix' }));
    expect(screen.queryByLabelText('Would you like to add your car?')).not.toBeInTheDocument();
    expect(screen.getByRole('slider', { name: 'Start driving' })).toHaveValue('9');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('heading', { name: 'Review', exact: true })).toHaveFocus();
    expect(screen.getByRole('progressbar', { name: 'Trip setup completion' })).toHaveAttribute(
      'value',
      '40'
    );
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Edit People' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Reset draft', exact: true }));
    await user.click(screen.getByRole('button', { name: 'Keep answers' }));
    expect(screen.getByRole('heading', { name: 'Review', exact: true })).toBeInTheDocument();
  });
  it('passes structured answers to address confirmation without generating a message', async () => {
    const draft = { ...validDraft(), interests: ['food'] };
    seed(draft, 4);
    const submit = vi.fn().mockResolvedValue({ ok: true });
    renderWithProviders(<TripSetup onSubmit={submit} />);
    await userEvent.click(screen.getByRole('button', { name: 'Check trip options' }));
    expect(submit).toHaveBeenCalledWith({ draft });
    expect(submit.mock.calls[0][0]).not.toHaveProperty('message');
    expect(screen.queryByText(/Continue in chat/)).not.toBeInTheDocument();
  });
  it('keeps address validation errors and draft answers', async () => {
    seed(validDraft(), 4);
    renderWithProviders(
      <TripSetup onSubmit={vi.fn().mockResolvedValue({ error: 'Location not found' })} />
    );
    await userEvent.click(screen.getByRole('button', { name: 'Check trip options' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Location not found');
    expect(sessionStorage.getItem(key())).not.toBeNull();
  });
  it('keeps the draft on a network failure, resets explicitly and removes account data on sign out', async () => {
    seed(validDraft(), 4);
    renderWithProviders(<TripSetup onSubmit={vi.fn().mockRejectedValue(new Error('offline'))} />);
    await userEvent.click(screen.getByRole('button', { name: 'Check trip options' }));
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
    await userEvent.click(screen.getByText('Adjust amounts'));
    const details = screen.getByText('Adjust amounts').closest('details');
    for (const [key, label] of Object.entries(INTERESTS)) {
      await userEvent.selectOptions(
        within(details).getByRole('combobox', { name: 'Interest to adjust' }),
        key
      );
      expect(within(details).getAllByRole('slider')).toHaveLength(1);
      fireEvent.change(within(details).getByRole('slider', { name: label }), {
        target: { value: '0' },
      });
    }
    await userEvent.click(screen.getByRole('button', { name: 'Done adjusting interests' }));
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('alert')).toHaveTextContent('above zero');
  });

  it('preserves exact saved manual amounts until an explicit action and keeps the existing profile blend', async () => {
    const customWeights = Object.fromEntries(
      Object.keys(INTERESTS).map((key, index) => [key, index === 0 ? 12000.123456789 : 0.123456789])
    );
    const draft = {
      ...validDraft(),
      customWeights,
      comparisonAnswers: { [COMPARISONS[0].id]: 'left' },
    };
    seed(draft, 2);
    renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
    await userEvent.click(screen.getByText('Adjust amounts'));
    const stored = () => JSON.parse(sessionStorage.getItem(key())).draft;
    expect(stored().customWeights).toEqual(customWeights);
    expect(preferenceWeights(stored())).toEqual(preferenceWeights(draft));
    const food = screen.getByRole('slider', { name: 'Food' });
    expect(Number(food.value)).toBe(customWeights.food);
    expect(Number(food.max)).toBeGreaterThan(Math.max(...Object.values(customWeights)));
    await userEvent.click(screen.getByRole('button', { name: 'More Food' }));
    const changed = stored();
    expect(changed.customWeights.food).toBeGreaterThan(customWeights.food);
    for (const interest of Object.keys(INTERESTS).filter((interest) => interest !== 'food'))
      expect(changed.customWeights[interest]).toBe(customWeights[interest]);
    expect(changed.comparisonAnswers).toEqual(draft.comparisonAnswers);
    const profiles = preferenceProfiles(changed);
    for (const interest of Object.keys(INTERESTS))
      expect(preferenceWeights(changed)[interest]).toBeCloseTo(
        (profiles.stated[interest] + profiles.comparisons[interest]) / 2,
        14
      );
    expect(screen.getByRole('heading', { name: 'What you enjoy' })).toBeInTheDocument();
    expect(screen.queryByRole('figure')).not.toBeInTheDocument();
  });

  it('seeds untouched interests at full precision on the first drag without submitting', async () => {
    const submit = vi.fn();
    const draft = { ...validDraft(), interests: ['food'] };
    seed(draft, 2);
    renderWithProviders(<TripSetup onSubmit={submit} />);
    await userEvent.click(screen.getByText('Adjust amounts'));
    const amounts = Object.fromEntries(
      Object.entries(preferenceProfiles(draft).stated).map(([interest, value]) => [
        interest,
        value * 100,
      ])
    );
    fireEvent.change(screen.getByRole('slider', { name: 'Food' }), {
      target: { value: '12.3456789' },
    });
    const changed = JSON.parse(sessionStorage.getItem(key())).draft;
    expect(changed.customWeights.food).toBe(12.3456789);
    for (const interest of Object.keys(INTERESTS).filter((interest) => interest !== 'food'))
      expect(changed.customWeights[interest]).toBe(amounts[interest]);
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'What you enjoy' })).toBeInTheDocument();
  });
});

it('requires valid road preparation before the first Next and retains the actionable route question on failure', async () => {
  seed(validDraft(), 0);
  const prepare = vi.fn().mockResolvedValueOnce({ ok: false }).mockResolvedValueOnce({ ok: true });
  renderWithProviders(<TripSetup onSubmit={vi.fn()} prepareRoute={prepare} />);
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(screen.getByRole('alert')).toHaveTextContent('usable road route');
  expect(screen.getByLabelText('Starting city or address')).toHaveValue('Boulder');
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(await screen.findByRole('heading', { name: 'People' })).toBeInTheDocument();
  expect(prepare).toHaveBeenCalledTimes(2);
});

it('groups attraction count with people and validates it before leaving that group', async () => {
  seed({ ...validDraft(), stops: '0' }, 1);
  renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
  expect(screen.getByLabelText('How many attractions would you like?')).toHaveValue(0);
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(screen.getByRole('alert')).toHaveFocus();
  expect(screen.getByRole('alert')).toHaveTextContent('Choose at least one attraction');
  fill('How many attractions would you like?', '4');
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(screen.getByRole('heading', { name: 'What you enjoy' })).toHaveFocus();
  expect(JSON.parse(sessionStorage.getItem(key())).draft.stops).toBe('4');
});

it('keeps compact visible interest names in their accessible names and preserves canonical keys', async () => {
  seed(validDraft(), 2);
  renderWithProviders(<TripSetup onSubmit={vi.fn()} />);
  for (const [visible, canonical, keyName] of [
    ['Scenery', 'Scenic views', 'scenery'],
    ['Arts', 'Art and culture', 'culture_arts'],
    ['Local places', 'Local discoveries', 'unique_local_experiences'],
    ['Quiet places', 'Quieter places', 'crowd_avoidance'],
  ]) {
    const control = screen.getByRole('checkbox', { name: `${visible} · ${canonical}` });
    expect(control.closest('label')).toHaveTextContent(visible);
    await userEvent.click(control);
    expect(JSON.parse(sessionStorage.getItem(key())).draft.interests).toContain(keyName);
  }
});
