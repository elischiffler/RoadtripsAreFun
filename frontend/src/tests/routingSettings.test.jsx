import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import GlobalHeader from '../components/GlobalHeader';
import { renderWithProviders } from './testUtils';
import {
  refreshRoutingSettings,
  invalidateRoutingSettings,
  chooseRoutingAlgorithm,
  getRoutingAlgorithm,
} from '../services/routingSettings';
import { getFinalRoute } from '../pages/ChatPage/getRoute';
import { sendAgentMessage } from '../pages/ChatPage/agentChat';

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const token = (sub, exp = Date.now() / 1000 + 600) =>
  `header.${btoa(JSON.stringify({ sub, exp }))}.fixture-signature`;
const capability = () => ({
  data: {
    can_select_algorithm: true,
    algorithms: ['cp_sat', 'test_alternate'],
    default: 'cp_sat',
    expires_at: Date.now() / 1000 + 600,
  },
});
const gear = () => screen.queryByRole('button', { name: 'routing algorithm settings' });
function login(sub = 'owner', exp) {
  sessionStorage.setItem('accessToken', token(sub, exp));
  sessionStorage.setItem('idToken', `identity-${sub}`);
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  localStorage.clear();
  invalidateRoutingSettings();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});
afterEach(() => {
  vi.useRealTimers();
  invalidateRoutingSettings();
  sessionStorage.clear();
});

describe('owner routing settings', () => {
  it.each(['missing', 'malformed', 'expired'])(
    'hides the gear for %s credentials',
    async (kind) => {
      if (kind === 'malformed') {
        sessionStorage.setItem('accessToken', 'bad');
        sessionStorage.setItem('idToken', 'bad');
      } else if (kind === 'expired') login('owner', 1);
      renderWithProviders(<GlobalHeader />);
      expect(gear()).not.toBeInTheDocument();
      expect(axios.get).not.toHaveBeenCalled();
      expect(getRoutingAlgorithm()).toBeNull();
    }
  );

  it('hides the gear with a missing identity token', () => {
    sessionStorage.setItem('accessToken', token('owner'));
    renderWithProviders(<GlobalHeader />);
    expect(gear()).not.toBeInTheDocument();
    expect(axios.get).not.toHaveBeenCalled();
  });

  it.each(['non-owner', 'invalid', 'unavailable'])(
    'fails closed for %s eligibility',
    async (kind) => {
      login();
      if (kind === 'non-owner')
        axios.get.mockResolvedValue({ data: { can_select_algorithm: false } });
      else axios.get.mockRejectedValue({ response: { status: kind === 'invalid' ? 401 : 503 } });
      renderWithProviders(<GlobalHeader />);
      await waitFor(() => expect(axios.get).toHaveBeenCalled());
      expect(gear()).not.toBeInTheDocument();
      expect(getRoutingAlgorithm()).toBeNull();
    }
  );

  it('grants access after login without a privileged flash and closes the picker on logout', async () => {
    let resolve;
    axios.get.mockImplementation(() => new Promise((done) => (resolve = done)));
    renderWithProviders(<GlobalHeader />);
    expect(gear()).not.toBeInTheDocument();
    act(() => {
      login();
      window.dispatchEvent(new Event('auth-changed'));
    });
    expect(gear()).not.toBeInTheDocument();
    await act(async () => resolve(capability()));
    expect(gear()).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(gear());
    expect(screen.getByText('active: cp_sat')).toBeInTheDocument();
    await user.click(screen.getByText('test_alternate'));
    expect(getRoutingAlgorithm()).toBe('test_alternate');
    await user.click(gear());
    act(() => {
      sessionStorage.clear();
      window.dispatchEvent(new Event('auth-changed'));
    });
    expect(gear()).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('test_alternate')).not.toBeInTheDocument());
    expect(getRoutingAlgorithm()).toBeNull();
  });

  it('discards a pending owner response after account switching', async () => {
    let resolveOwner;
    login();
    axios.get.mockImplementationOnce(() => new Promise((done) => (resolveOwner = done)));
    axios.get.mockResolvedValue({ data: { can_select_algorithm: false } });
    renderWithProviders(<GlobalHeader />);
    act(() => {
      login('other');
      window.dispatchEvent(new Event('auth-changed'));
    });
    await act(async () => resolveOwner(capability()));
    expect(gear()).not.toBeInTheDocument();
    expect(getRoutingAlgorithm()).toBeNull();
  });

  it('invalidates an open owner picker and selection when credentials expire', async () => {
    login('owner', Date.now() / 1000 + 30);
    axios.get.mockResolvedValue(capability());
    renderWithProviders(<GlobalHeader />);
    await waitFor(() => expect(gear()).toBeInTheDocument());
    chooseRoutingAlgorithm('test_alternate');
    vi.useFakeTimers();
    act(() => {
      vi.setSystemTime(Date.now() + 31000);
      window.dispatchEvent(new Event('focus'));
    });
    expect(gear()).not.toBeInTheDocument();
    expect(getRoutingAlgorithm()).toBeNull();
  });

  it('ignores tampered storage and request context for non-owners in both request paths', async () => {
    login('other');
    localStorage.setItem('devRoutingAlgorithm', 'test_alternate');
    axios.get.mockResolvedValue({ data: { can_select_algorithm: false } });
    axios.post.mockResolvedValue({ data: {} });
    await refreshRoutingSettings();
    chooseRoutingAlgorithm('test_alternate');
    await getFinalRoute({}, 100, 0);
    await sendAgentMessage({
      accessToken: sessionStorage.getItem('accessToken'),
      chatId: 'chat',
      message: 'plan',
      clientContext: { algorithm: 'test_alternate', hasRoute: true },
    });
    expect(axios.post.mock.calls[0][1]).not.toHaveProperty('algorithm');
    expect(axios.post.mock.calls[1][1].clientContext).toEqual({ hasRoute: true });
    expect(localStorage.getItem('devRoutingAlgorithm')).toBeNull();
  });

  it('sends only an explicit registered owner selection in direct and chat requests', async () => {
    login();
    axios.get.mockResolvedValue(capability());
    axios.post.mockResolvedValue({ data: {} });
    await refreshRoutingSettings();
    expect(getRoutingAlgorithm()).toBeNull();
    chooseRoutingAlgorithm('unknown');
    expect(getRoutingAlgorithm()).toBeNull();
    chooseRoutingAlgorithm('test_alternate');
    await getFinalRoute({}, 100, 0);
    await sendAgentMessage({
      accessToken: sessionStorage.getItem('accessToken'),
      chatId: 'chat',
      message: 'plan',
      clientContext: {},
    });
    expect(axios.post.mock.calls[0][1].algorithm).toBe('test_alternate');
    expect(axios.post.mock.calls[1][1].clientContext.algorithm).toBe('test_alternate');
    expect(axios.post.mock.calls[1][2].headers['X-Cognito-Id-Token']).toBe('identity-owner');
    login('other');
    expect(getRoutingAlgorithm()).toBeNull();
  });
});
