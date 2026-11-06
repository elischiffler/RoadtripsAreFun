import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { invalidateRoutingSettings } from '../services/routingSettings';
import { signOut } from '../services/session';
import SettingsPage from '../pages/SettingsPage';
import ResearchAccess from '../components/ResearchAccess';
import AuthWrapper from '../components/AuthWrapper';

vi.mock('../services/preferenceProfiles', () => ({
  loadPreferenceProfiles: vi.fn(async () => []),
  savePreferenceProfile: vi.fn(),
  deletePreferenceProfile: vi.fn(),
}));
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const capability = (allowed) => ({
  data: {
    can_select_algorithm: allowed,
    algorithms: ['cp_sat'],
    default: 'cp_sat',
    expires_at: Date.now() / 1000 + 600,
  },
});
beforeEach(() => {
  sessionStorage.clear();
  invalidateRoutingSettings();
  vi.clearAllMocks();
  fixtureSession('owner');
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});
afterEach(() => {
  invalidateRoutingSettings();
  sessionStorage.clear();
});

it('keeps regular settings available while owner capability is pending, then adds research links', async () => {
  let resolve;
  axios.get.mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  renderWithProviders(<SettingsPage />, { initialPath: '/settings' });
  expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Plan a trip' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Trip preferences' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'AI Studio' })).not.toBeInTheDocument();
  await waitFor(() => expect(resolve).toBeTypeOf('function'));
  await act(async () => resolve(capability(true)));
  expect(screen.getByRole('link', { name: 'AI Studio' })).toHaveAttribute('href', '/studio');
  expect(screen.getByRole('link', { name: 'Trip research' })).toHaveAttribute(
    'href',
    '/studio/research'
  );
  act(() => signOut());
  expect(screen.queryByRole('link', { name: 'AI Studio' })).not.toBeInTheDocument();
});

it.each(['non-owner', 'forged-email', 'server-failure'])(
  'does not grant research access for %s',
  async (kind) => {
    fixtureSession('other');
    if (kind === 'forged-email') {
      const token = sessionStorage.getItem('idToken').split('.');
      token[1] = btoa(
        JSON.stringify({
          ...JSON.parse(atob(token[1])),
          email: 'eschiffler1122@gmail.com',
          email_verified: true,
        })
      );
      sessionStorage.setItem('idToken', token.join('.'));
      localStorage.setItem('devRoutingAlgorithm', 'cp_sat');
    }
    if (kind === 'server-failure') axios.get.mockRejectedValue(new Error('offline'));
    else axios.get.mockResolvedValue(capability(false));
    renderWithProviders(
      <>
        <SettingsPage />
        <ResearchAccess>
          <p>Private tools mounted</p>
        </ResearchAccess>
      </>,
      { initialPath: '/studio/research' }
    );
    expect(screen.queryByText('Private tools mounted')).not.toBeInTheDocument();
    await screen.findByRole('alert');
    expect(screen.queryByText('Private tools mounted')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /AI Studio|Trip research/ })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
  }
);

it('mounts tools only after server approval and unmounts them immediately when the account changes', async () => {
  axios.get.mockResolvedValue(capability(true));
  renderWithProviders(
    <ResearchAccess>
      <p>Private tools mounted</p>
    </ResearchAccess>,
    { initialPath: '/studio' }
  );
  expect(screen.queryByText('Private tools mounted')).not.toBeInTheDocument();
  await screen.findByText('Private tools mounted');
  axios.get.mockResolvedValue(capability(false));
  act(() => fixtureSession('other'));
  expect(screen.queryByText('Private tools mounted')).not.toBeInTheDocument();
  await screen.findByRole('alert');
});

it('keeps unauthenticated direct visitors outside both the capability guard and private tools', async () => {
  signOut();
  renderWithProviders(
    <AuthWrapper>
      <ResearchAccess>
        <p>Private tools mounted</p>
      </ResearchAccess>
    </AuthWrapper>,
    { initialPath: '/studio' }
  );
  expect(screen.queryByText('Private tools mounted')).not.toBeInTheDocument();
  expect(axios.get).not.toHaveBeenCalled();
});
