import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { useContext } from 'react';
import { Routes, Route } from 'react-router-dom';
import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import { cognitoClient } from '../services/cognito';
import { ensureSession, getSession, signOut } from '../services/session';
import { fixtureSession, fixtureToken } from './sessionFixtures';
import AuthWrapper from '../components/AuthWrapper';
import ChatInput from '../pages/ChatPage/ChatInput';
import LoginPage from '../pages/AuthPages/LoginPage';
import { ChatData, Data, ChatLogs, UserDataContext } from '../states/UserDataContext';

vi.mock('../services/cognito', () => ({ cognitoClient: { send: vi.fn() } }));
beforeEach(() => {
  signOut();
  sessionStorage.clear();
  vi.resetAllMocks();
});
afterEach(() => signOut());
const reply = (owner = 'user') => ({
  AuthenticationResult: {
    AccessToken: fixtureToken(owner),
    IdToken: fixtureToken(owner, undefined, 'id'),
    RefreshToken: 'new-refresh',
  },
});
function ProtectedTrip() {
  const { UserData, setUserData, chats, setChats } = useContext(UserDataContext);
  const trip = UserData.chatlogs.getChatDataById(4);
  return (
    <>
      <button
        onClick={() => {
          const trip = new ChatData(4);
          trip.route = { name: 'Coastal route' };
          trip.agentChatId = 'conversation';
          setUserData(new Data(new ChatLogs([trip], 4)));
          setChats([{ id: 4, title: 'My trip', messages: [] }]);
          sessionStorage.setItem('selectedChatId', '4');
        }}
      >
        Seed trip
      </button>
      <output>
        {trip?.route?.name ?? 'No route'}; {chats.length} chats;{' '}
        {trip?.agentChatId ?? 'No conversation'}
      </output>
      <ChatInput draftKey="conversation" onSubmit={vi.fn()} />
      <button
        onClick={() =>
          void ensureSession({ rejectedToken: getSession().accessToken }).catch(() => {})
        }
      >
        Expire session
      </button>
    </>
  );
}
function renderRecovery() {
  return renderWithProviders(
    <Routes>
      <Route
        path="/chat"
        element={
          <AuthWrapper>
            <ProtectedTrip />
          </AuthWrapper>
        }
      />
      <Route path="/login" element={<LoginPage />} />
    </Routes>,
    { initialPath: '/chat' }
  );
}

it('waits for restoration before mounting protected children', async () => {
  fixtureSession('user', undefined, 'refresh');
  sessionStorage.removeItem('accessToken');
  let resolve;
  cognitoClient.send.mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  renderRecovery();
  expect(screen.getByText('Restoring your session...')).toBeInTheDocument();
  expect(screen.queryByRole('textbox', { name: 'Chat message' })).not.toBeInTheDocument();
  await act(async () => resolve(reply()));
  expect(await screen.findByRole('textbox', { name: 'Chat message' })).toBeInTheDocument();
});
it.each(['user', 'other'])(
  'preserves the trip and unsent draft only when signing back in as %s',
  async (owner) => {
    fixtureSession('user', undefined, 'refresh');
    const user = userEvent.setup();
    renderRecovery();
    await user.click(await screen.findByText('Seed trip'));
    await user.type(
      screen.getByRole('textbox', { name: 'Chat message' }),
      'Keep my unsent message'
    );
    cognitoClient.send.mockRejectedValueOnce({ name: 'NotAuthorizedException' });
    await user.click(screen.getByText('Expire session'));
    expect(await screen.findByText(/Your session expired/)).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Chat message' })).not.toBeInTheDocument();
    cognitoClient.send.mockResolvedValueOnce(reply(owner));
    await user.type(screen.getByLabelText(/Email/), 'test@example.com');
    await user.type(document.querySelector('input[type=password]'), 'password');
    await user.click(screen.getByRole('button', { name: 'Log In' }));
    const input = await screen.findByRole('textbox', { name: 'Chat message' });
    if (owner === 'user') {
      expect(input).toHaveValue('Keep my unsent message');
      expect(screen.getByText('Coastal route; 1 chats; conversation')).toBeInTheDocument();
      expect(sessionStorage.getItem('selectedChatId')).toBe('4');
    } else {
      expect(input).toHaveValue('');
      expect(screen.getByText('No route; 0 chats; No conversation')).toBeInTheDocument();
      expect(sessionStorage.getItem('selectedChatId')).toBeNull();
    }
  }
);
it('keeps an outage on the protected route and recovers through the retry action', async () => {
  fixtureSession('user', undefined, 'refresh');
  sessionStorage.removeItem('accessToken');
  cognitoClient.send.mockRejectedValue(new TypeError('offline'));
  renderRecovery();
  expect(await screen.findByRole('alert')).toHaveTextContent('temporarily unavailable');
  expect(screen.queryByText('Log In')).not.toBeInTheDocument();
  expect(getSession().refreshToken).toBe('refresh');
  const now = Date.now();
  vi.spyOn(Date, 'now').mockReturnValue(now + 6000);
  cognitoClient.send.mockResolvedValue(reply());
  await userEvent.setup().click(screen.getByRole('button', { name: 'Retry' }));
  await waitFor(() =>
    expect(screen.getByRole('textbox', { name: 'Chat message' })).toBeInTheDocument()
  );
});
