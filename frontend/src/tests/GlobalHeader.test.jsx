/**
 * GlobalHeader — top navigation bar tests.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import GlobalHeader from '../components/GlobalHeader';
import { useContext } from 'react';
import { ChatData, Data, ChatLogs, UserDataContext } from '../states/UserDataContext';

function TripStateProbe() {
  const { chats, UserData, setChats, setUserData } = useContext(UserDataContext);
  return (
    <>
      <button
        onClick={() => {
          setChats([{ id: 741, title: 'Private coastal trip', messages: [] }]);
          setUserData(new Data(new ChatLogs([new ChatData(741)])));
          sessionStorage.setItem('selectedChatId', '741');
        }}
      >
        Seed private trip
      </button>
      <output>{`${chats.length} chats; ${UserData.chatlogs.chatdata.length} trip records`}</output>
    </>
  );
}

describe('GlobalHeader', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  it('is hidden on the /login route', () => {
    renderWithProviders(<GlobalHeader />, { initialPath: '/login' });
    // The header returns null on /login — nothing should render
    expect(document.querySelector('.global-header')).not.toBeInTheDocument();
  });

  it('is hidden on the /signup route', () => {
    renderWithProviders(<GlobalHeader />, { initialPath: '/signup' });
    expect(document.querySelector('.global-header')).not.toBeInTheDocument();
  });

  it('shows a Login button when unauthenticated', () => {
    renderWithProviders(<GlobalHeader />, { initialPath: '/' });
    expect(screen.getByRole('link', { name: /login/i })).toBeInTheDocument();
  });

  it('shows the avatar when authenticated', () => {
    sessionStorage.setItem('accessToken', 'fake-token');
    renderWithProviders(<GlobalHeader />, { initialPath: '/chat' });
    // The avatar renders a "U" placeholder
    expect(screen.getByText('U')).toBeInTheDocument();
  });

  it('clears tokens and closes menu on Sign out click', async () => {
    sessionStorage.setItem('accessToken', 'fake-token');
    sessionStorage.setItem('idToken', 'id-tok');
    sessionStorage.setItem('refreshToken', 'ref-tok');
    const user = userEvent.setup();

    renderWithProviders(<GlobalHeader />, { initialPath: '/chat' });

    // Open profile menu
    await user.click(screen.getByText('U'));
    // Click Sign out
    await user.click(screen.getByText(/sign out/i));

    await waitFor(() => {
      expect(sessionStorage.getItem('accessToken')).toBeNull();
      expect(sessionStorage.getItem('idToken')).toBeNull();
      expect(sessionStorage.getItem('refreshToken')).toBeNull();
    });
  });

  it('removes the previous owner trip from client state on sign out', async () => {
    sessionStorage.setItem('accessToken', 'owner-token');
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <GlobalHeader />
        <TripStateProbe />
      </>,
      { initialPath: '/chat' }
    );
    await user.click(screen.getByText('Seed private trip'));
    expect(screen.getByText('1 chats; 1 trip records')).toBeInTheDocument();
    await user.click(screen.getByText('U'));
    await user.click(screen.getByText(/sign out/i));
    expect(screen.getByText('0 chats; 0 trip records')).toBeInTheDocument();
    expect(sessionStorage.getItem('selectedChatId')).toBeNull();
  });
});
