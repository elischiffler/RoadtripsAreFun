import { useContext, useEffect, useState } from 'react';
import { Box, Button, Container, Typography } from '@mui/material';
import { Link } from 'react-router-dom';
import { UserDataContext } from '../states/UserDataContext';
import { initializeUserData } from '../services/savedTrips';
import { getSession, isCurrentSession } from '../services/session';

export default function SavedTripsPage() {
  const { UserData, setUserData, chats, setChats } = useContext(UserDataContext);
  const [status, setStatus] = useState('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const session = getSession();
    setStatus('loading');
    initializeUserData(session.accessToken).then((result) => {
      if (cancelled || !isCurrentSession(session)) return;
      if (!result) {
        setStatus('error');
        return;
      }
      const logs = result.UserData.chatlogs;
      const selected = Number(sessionStorage.getItem('selectedChatId'));
      logs.currentId = logs.getChatDataById(selected) ? selected : logs.chatdata[0]?.chatId;
      setUserData(result.UserData);
      setChats(result.chats);
      setStatus('ready');
    });
    return () => {
      cancelled = true;
    };
  }, [attempt, setUserData, setChats]);

  const selectTrip = (id) => {
    UserData.chatlogs.currentId = id;
    sessionStorage.setItem('selectedChatId', String(id));
  };

  return (
    <Container sx={{ pt: 14, pb: 5 }}>
      <Typography variant="h1" sx={{ fontSize: '2rem', mb: 3 }}>
        Saved trips
      </Typography>
      <Button component={Link} to="/plan" variant="contained" sx={{ mb: 3 }}>
        Plan a trip
      </Button>
      {status === 'loading' && <Typography role="status">Loading saved trips…</Typography>}
      {status === 'error' && (
        <Box role="alert">
          <Typography>Saved trips could not be loaded.</Typography>
          <Button onClick={() => setAttempt((value) => value + 1)}>Retry loading trips</Button>
        </Box>
      )}
      {status === 'ready' && !chats.length && <Typography>No saved trips yet.</Typography>}
      {status === 'ready' && (
        <Box component="ul" sx={{ listStyle: 'none', p: 0 }}>
          {chats.map((trip) => {
            const data = UserData.chatlogs.getChatDataById(trip.id);
            return (
              <Box
                component="li"
                key={trip.id}
                sx={{ p: 2, mb: 2, border: '1px solid', borderRadius: 2 }}
              >
                <Typography variant="h2" sx={{ fontSize: '1.25rem', mb: 1 }}>
                  {trip.title || `Trip ${trip.id}`}
                </Typography>
                {data?.route && (
                  <Button component={Link} to="/map" onClick={() => selectTrip(trip.id)}>
                    View map
                  </Button>
                )}
                {data?.itinerary && (
                  <Button component={Link} to="/itinerary" onClick={() => selectTrip(trip.id)}>
                    View itinerary
                  </Button>
                )}
                {!data?.route && !data?.itinerary && (
                  <Typography>
                    Trip details are saved. No route or itinerary is available.
                  </Typography>
                )}
              </Box>
            );
          })}
        </Box>
      )}
    </Container>
  );
}
