import { useContext, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { DesignFrame } from '../design';
import './SavedTripsPage.css';
import { Link } from 'react-router-dom';
import { UserDataContext, Data, ChatLogs } from '../states/UserDataContext';
import { initializeUserData, deleteChat } from '../services/savedTrips';
import { getSession, isCurrentSession } from '../services/session';

export default function SavedTripsPage() {
  const { UserData, setUserData, chats, setChats } = useContext(UserDataContext);
  const [status, setStatus] = useState('loading');
  const [attempt, setAttempt] = useState(0);
  const [deleting, setDeleting] = useState(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState('');

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

  const confirmDelete = async () => {
    if (!deleting || deletePending) return;
    const session = getSession();
    const logs = UserData.chatlogs;
    setDeletePending(true);
    setDeleteError('');
    const removed = await deleteChat(session.accessToken, deleting.id, logs);
    if (!isCurrentSession(session)) return;
    setDeletePending(false);
    if (!removed) {
      setDeleteError('Trip could not be deleted. Try again.');
      return;
    }
    logs.removeChatData(deleting.id);
    if (logs.currentId === deleting.id) {
      logs.currentId = logs.chatdata[0]?.chatId;
      if (logs.currentId != null) sessionStorage.setItem('selectedChatId', String(logs.currentId));
      else sessionStorage.removeItem('selectedChatId');
    }
    setUserData(new Data(new ChatLogs([...logs.chatdata], logs.currentId)));
    setChats((previous) => previous.filter((trip) => trip.id !== deleting.id));
    setDeleting(null);
  };

  return (
    <DesignFrame className="saved-trips-page">
      <main className="rt-stack">
        <Typography variant="h1" className="rt-display">
          Saved trips
        </Typography>
        <Button component={Link} to="/plan" variant="contained" className="saved-trips-plan">
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
          <Box component="ul" className="saved-trip-list">
            {chats.map((trip) => {
              const data = UserData.chatlogs.getChatDataById(trip.id);
              const origin = data?.startConfirmed?.address || data?.tripProfile?.start_address;
              const destination =
                data?.endConfirmed?.address || data?.tripProfile?.destination_address;
              const departure = data?.tripProfile?.start_date?.slice(0, 10);
              const days = Array.isArray(data?.itinerary) ? data.itinerary : [];
              const dateLabel = days.length
                ? [...new Set([days[0].date, days.at(-1).date].filter(Boolean))].join(' – ')
                : departure;
              return (
                <Box component="li" key={trip.id} className="saved-trip-card">
                  <Typography variant="h2" className="rt-title">
                    {trip.title || `Trip ${trip.id}`}
                  </Typography>
                  <Typography className="saved-trip-endpoints">
                    {origin || 'Start not set'} → {destination || 'Destination not set'}
                  </Typography>
                  <Typography className="saved-trip-date">
                    {dateLabel || 'Dates not set'}
                  </Typography>
                  <Box className="saved-trip-actions">
                    <Button component={Link} to="/trip" onClick={() => selectTrip(trip.id)}>
                      Open trip
                    </Button>
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
                    <Button
                      onClick={() => {
                        setDeleting(trip);
                        setDeleteError('');
                      }}
                      aria-label={`Delete ${trip.title || `Trip ${trip.id}`}`}
                    >
                      Delete
                    </Button>
                  </Box>
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
      </main>
      <Dialog
        open={Boolean(deleting)}
        onClose={() => {
          if (!deletePending) setDeleting(null);
        }}
        aria-labelledby="delete-trip-title"
        aria-describedby="delete-trip-description"
      >
        <DialogTitle id="delete-trip-title">Delete {deleting?.title || 'trip'}?</DialogTitle>
        <DialogContent>
          <Typography id="delete-trip-description">
            This permanently deletes the saved trip and its itinerary.
          </Typography>
          {deleteError && <Typography role="alert">{deleteError}</Typography>}
        </DialogContent>
        <DialogActions>
          <Button autoFocus disabled={deletePending} onClick={() => setDeleting(null)}>
            Cancel
          </Button>
          <Button disabled={deletePending} onClick={confirmDelete}>
            {deletePending ? 'Deleting…' : 'Delete trip'}
          </Button>
        </DialogActions>
      </Dialog>
    </DesignFrame>
  );
}
