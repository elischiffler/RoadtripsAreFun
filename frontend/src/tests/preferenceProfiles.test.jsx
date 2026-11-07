import { beforeEach, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from '../services/protectedRequest';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { signOut } from '../services/session';
import { newSetupDraft, preferenceWeights } from '../pages/TripSetup/setupModel';
import {
  applyPreferenceChoices,
  choicesFromDraft,
  samePreferenceChoices,
  saveNewTripPreferences,
} from '../services/preferenceProfiles';
import SettingsPage from '../pages/SettingsPage';
import { initializeUserData } from '../services/savedTrips';
import PreferenceProfilePicker from '../components/PreferenceProfilePicker';
import AppTheme from '../components/AppTheme';
import { setThemeMode } from '../services/themeMode';

vi.mock('../services/savedTrips', () => ({ initializeUserData: vi.fn(async () => null) }));
vi.mock('../services/protectedRequest', () => ({
  default: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock('../services/routingSettings', () => ({
  useRoutingSettings: () => ({ canSelect: false }),
}));
const draft = () => ({
  ...newSetupDraft(),
  carStatus: 'provided',
  year: '2020',
  make: 'Honda',
  model: 'Civic',
  interests: ['nature'],
});
const profile = () => ({
  id: '2c2d62ef-2d97-473b-a7a0-8d328ade84ed',
  name: 'Weekend car',
  choices: choicesFromDraft(draft()),
});
beforeEach(() => {
  vi.resetAllMocks();
  initializeUserData.mockResolvedValue(null);
  sessionStorage.clear();
  fixtureSession('account-a');
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
  axios.get.mockResolvedValue({ data: [] });
  axios.put.mockImplementation(async (_, data) => ({ data }));
  axios.delete.mockResolvedValue({});
  setThemeMode('light');
});

it('copies only reusable choices and preserves all route, date, traveler and budget answers', () => {
  const current = {
    ...newSetupDraft(),
    start: 'Boulder',
    destination: 'Denver',
    stops: '5',
    date: '2027-07-01',
    time: '11:00',
    budget: '175',
    travelers: '2',
    rooms: [{ adults: '2', children: '' }],
  };
  const loaded = applyPreferenceChoices(current, profile().choices);
  for (const key of [
    'start',
    'destination',
    'stops',
    'date',
    'time',
    'budget',
    'travelers',
    'rooms',
  ])
    expect(loaded[key]).toEqual(current[key]);
  expect(loaded.carStatus).toBe('provided');
  expect(loaded.year).toBe('2020');
  expect(preferenceWeights(loaded)).toEqual(preferenceWeights(draft()));
  expect(loaded.comparisonAnswers).toEqual({});
  expect(Object.keys(choicesFromDraft(draft())).sort()).toEqual([
    'car',
    'car_status',
    'persona_weights',
    'scheduling_policy',
  ]);
});

it('saves each distinct set and reuses matching sets, including normalization rounding', async () => {
  await saveNewTripPreferences(draft(), profile().id);
  expect(axios.put).toHaveBeenCalledTimes(1);
  expect(axios.put.mock.calls[0][1]).toEqual({
    name: '2020 Honda Civic · Nature + Scenic views',
    choices: profile().choices,
  });
  axios.get.mockResolvedValue({ data: [profile()] });
  await saveNewTripPreferences(draft(), crypto.randomUUID());
  expect(axios.put).toHaveBeenCalledTimes(1);
  const reordered = JSON.parse(JSON.stringify(profile().choices));
  reordered.persona_weights.nature += 1e-16;
  expect(samePreferenceChoices(profile().choices, reordered)).toBe(true);
});

it('does not save old preferences to a new account after an asynchronous lookup', async () => {
  let finish;
  axios.get.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const saving = saveNewTripPreferences(draft(), profile().id);
  fixtureSession('account-b');
  finish({ data: [] });
  await expect(saving).rejects.toThrow('Session renewal is temporarily unavailable');
  expect(axios.put).not.toHaveBeenCalled();
});

it('edits and deletes a profile without a trip-planning redirect or trip mutation', async () => {
  axios.get.mockResolvedValue({ data: [profile()] });
  renderWithProviders(<SettingsPage />);
  await screen.findByRole('heading', { name: 'Weekend car' });
  expect(screen.queryByRole('link', { name: 'Plan a trip' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Edit Weekend car' }));
  await userEvent.clear(screen.getByLabelText('Profile name'));
  await userEvent.type(screen.getByLabelText('Profile name'), 'Family weekends');
  await userEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await screen.findByText('Preferences saved.');
  expect(axios.put).toHaveBeenCalledWith(
    expect.stringContaining(profile().id),
    expect.objectContaining({ name: 'Family weekends' }),
    expect.any(Object)
  );
  await userEvent.click(screen.getByRole('button', { name: 'Delete Weekend car' }));
  expect(axios.delete).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));
  await screen.findByText('Preferences deleted.');
  expect(axios.delete).toHaveBeenCalledWith(
    expect.stringContaining(profile().id),
    expect.any(Object)
  );
});

it('creates preferences, handles a failed save and keeps editing for retry', async () => {
  axios.put.mockRejectedValueOnce(new Error('offline'));
  renderWithProviders(<SettingsPage />);
  await screen.findByText('No saved preferences yet.');
  await userEvent.click(screen.getByRole('button', { name: 'New preferences' }));
  await userEvent.type(screen.getByLabelText('Profile name'), 'Quiet roads');
  await userEvent.click(screen.getByText('Interests', { selector: 'summary' }));
  await userEvent.click(screen.getByLabelText('Quieter places'));
  await userEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Profile name')).toHaveValue('Quiet roads');
  await userEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await screen.findByText('Preferences saved.');
  expect(axios.put.mock.calls[0][0]).toEqual(axios.put.mock.calls[1][0]);
});

it('clears the profile list and editor immediately on account change, ignoring late results', async () => {
  axios.get.mockResolvedValueOnce({ data: [profile()] });
  let finish;
  axios.get.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const view = renderWithProviders(<SettingsPage />);
  await screen.findByRole('heading', { name: 'Weekend car' });
  await userEvent.click(screen.getByRole('button', { name: 'Edit Weekend car' }));
  act(() => fixtureSession('account-b'));
  expect(screen.queryByRole('heading', { name: 'Weekend car' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Profile name')).not.toBeInTheDocument();
  act(() => signOut());
  await act(async () => finish({ data: [profile()] }));
  expect(screen.queryByText('Weekend car')).not.toBeInTheDocument();
  view.unmount();
});

function Picker() {
  const [value, setValue] = useState({ ...newSetupDraft(), start: 'Boulder', stops: '4' });
  return (
    <>
      <PreferenceProfilePicker setDraft={setValue} />
      <p>
        {value.start} / {value.stops} / {value.model}
      </p>
    </>
  );
}
it('offers explicit profile loading while preserving trip input', async () => {
  axios.get.mockResolvedValue({ data: [profile()] });
  renderWithProviders(<Picker />);
  await screen.findByLabelText('Saved preferences');
  await waitFor(() =>
    expect(screen.getByRole('option', { name: 'Weekend car' })).toBeInTheDocument()
  );
  await userEvent.selectOptions(screen.getByLabelText('Saved preferences'), profile().id);
  await userEvent.click(screen.getByRole('button', { name: 'Load preferences' }));
  expect(screen.getByText('Boulder / 4 / Civic')).toBeInTheDocument();
});

it('updates both the document theme and browser preference through settings', async () => {
  renderWithProviders(
    <AppTheme>
      <SettingsPage />
    </AppTheme>
  );
  await screen.findByText('No saved preferences yet.');
  await userEvent.click(screen.getByRole('radio', { name: 'Dark' }));
  expect(document.documentElement.dataset.theme).toBe('dark');
  expect(localStorage.getItem('roadtrips.theme')).toBe('dark');
  expect(document.documentElement.style.getPropertyValue('--cream-light')).toBe('#111c18');
  await userEvent.click(screen.getByRole('radio', { name: 'Light' }));
  expect(document.documentElement.dataset.theme).toBe('light');
});
