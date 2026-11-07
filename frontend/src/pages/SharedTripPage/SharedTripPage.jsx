import { useEffect, useLayoutEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ActionButton, DesignFrame, Field, Sheet } from '../../design';
import { getSession, isCurrentSession } from '../../services/session';
import { useSessionStatus } from '../../services/useSessionStatus';
import PlaceTiming from '../../components/PlaceTiming';
import {
  captureShareToken,
  clearShareToken,
  connectSharedTrip,
  leaveSharedTrip,
  sharingError,
  viewConnectedTrip,
  viewShareLink,
} from '../../services/tripSharing';
import './Sharing.css';

export default function SharedTripPage() {
  const { shareId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const session = useSessionStatus();
  const [token, setToken] = useState(() => (shareId ? null : captureShareToken(location.hash)));
  useLayoutEffect(() => {
    if (!shareId && location.hash) {
      setToken(captureShareToken(location.hash));
      window.history.replaceState(
        window.history.state,
        '',
        window.location.pathname + window.location.search
      );
    }
  }, [shareId, location.hash]);
  const key = shareId ? `${session.owner}:${shareId}` : token;
  const [record, setRecord] = useState(null);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const view = record?.key === key ? record.data : null;
  useEffect(() => {
    setName('');
    setBusy(false);
  }, [session.owner]);
  useEffect(() => {
    const controller = new AbortController();
    const started = getSession();
    setRecord(null);
    setError('');
    if (!shareId && !token) {
      setError('Open the complete sharing link from the trip owner.');
      return () => controller.abort();
    }
    const load = shareId
      ? viewConnectedTrip(shareId, controller.signal)
      : viewShareLink(token, controller.signal);
    load
      .then((data) => {
        if (!controller.signal.aborted && (!shareId || isCurrentSession(started)))
          setRecord({ key, data });
      })
      .catch((failure) => {
        if (!controller.signal.aborted && (!shareId || isCurrentSession(started)))
          setError(sharingError(failure));
      });
    return () => controller.abort();
  }, [shareId, token, key, attempt]);
  const connect = async (event) => {
    event.preventDefault();
    if (busy) return;
    const started = getSession();
    setBusy(true);
    setError('');
    try {
      const result = await connectSharedTrip(token, name.trim());
      if (isCurrentSession(started)) {
        clearShareToken();
        navigate(`/shared-trips/${result.share_id}`, { replace: true });
      }
    } catch (failure) {
      if (isCurrentSession(started)) setError(sharingError(failure));
    } finally {
      if (isCurrentSession(started)) setBusy(false);
    }
  };
  const leave = async () => {
    const started = getSession();
    setBusy(true);
    try {
      await leaveSharedTrip(shareId);
      if (isCurrentSession(started)) navigate('/shared-trips', { replace: true });
    } catch (failure) {
      if (isCurrentSession(started)) setError(sharingError(failure));
    } finally {
      if (isCurrentSession(started)) setBusy(false);
    }
  };
  const coordinates = view?.route?.coordinates || [];
  const xs = coordinates.map(([x]) => x);
  const ys = coordinates.map(([, y]) => y);
  const west = Math.min(...xs),
    east = Math.max(...xs),
    south = Math.min(...ys),
    north = Math.max(...ys);
  const outline = coordinates
    .map(
      ([x, y]) =>
        `${20 + ((x - west) / (east - west || 1)) * 360},${180 - ((y - south) / (north - south || 1)) * 160}`
    )
    .join(' ');
  return (
    <DesignFrame>
      <header className="rt-stack">
        <h1 className="rt-display">Shared trip</h1>
        <p className="rt-copy">
          Read-only. Refresh to see the owner’s latest schedule. Only the owner can edit this trip.
        </p>
        <Link className="sharing-link" to="/shared-trips">
          Trips connected to your account
        </Link>
      </header>
      {error && (
        <p role="alert" className="rt-copy">
          {error}
        </p>
      )}
      {!view && !error && <p role="status">Loading shared trip…</p>}
      <ActionButton variant="secondary" disabled={busy} onClick={() => setAttempt((v) => v + 1)}>
        Refresh shared trip
      </ActionButton>
      {view && (
        <>
          <Sheet>
            <h2 className="rt-title">{view.title}</h2>
            {!!coordinates.length && (
              <svg
                className="shared-route-outline"
                viewBox="0 0 400 200"
                role="img"
                aria-label="Shared route outline"
              >
                <polyline
                  points={outline}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
            <p className="rt-caption">
              Route outline, not turn-by-turn navigation. No live location is shown or collected.
            </p>
          </Sheet>
          {view.itinerary.map((day, index) => (
            <Sheet key={index} aria-label={`Schedule for ${day.date}`}>
              <h2 className="rt-title">{day.date}</h2>
              <ol className="shared-timeline">
                {day.stops.map((stop, stopIndex) => (
                  <li key={stopIndex}>
                    <p className="rt-title">{stop.name}</p>
                    <PlaceTiming place={stop} />
                    {!stop.arrival_time && !stop.departure_time && (
                      <p className="rt-copy">
                        {stop.time}
                        {stop.timezone ? ` · ${stop.timezone}` : ''}
                      </p>
                    )}
                    {stop.kind === 'meal' && (
                      <p className="rt-caption">Meal break. No dining place selected or booked.</p>
                    )}
                  </li>
                ))}
              </ol>
            </Sheet>
          ))}
          {!shareId && (
            <Sheet aria-label="Connect your account">
              <h2 className="rt-title">Keep this trip with your account</h2>
              <p className="rt-copy">
                Connecting lets you reopen the same trip without this link. It grants read-only
                access until you leave or the owner removes your connection.
              </p>
              {session.owner ? (
                <form className="rt-stack" onSubmit={connect}>
                  <Field
                    label="Your name for this trip's owner"
                    value={name}
                    maxLength={80}
                    required
                    onChange={(event) => setName(event.target.value)}
                    hint="A display label, not an invitation or account lookup."
                  />
                  <ActionButton type="submit" disabled={busy || !name.trim()}>
                    Connect my account
                  </ActionButton>
                </form>
              ) : (
                <Link className="sharing-link" to="/login" state={{ returnTo: '/share' }}>
                  Sign in to connect this trip
                </Link>
              )}
            </Sheet>
          )}
          {shareId && (
            <ActionButton variant="secondary" disabled={busy} onClick={leave}>
              Leave shared trip
            </ActionButton>
          )}
        </>
      )}
    </DesignFrame>
  );
}
