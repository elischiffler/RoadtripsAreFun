import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { ActionButton, DesignFrame } from '../../design';
import { listSharedTrips } from '../../services/tripSharing';
import { initializeUserData } from '../../services/savedTrips';
import { getSession, isCurrentSession } from '../../services/session';
import './HomePage.css';

/** Enter planning directly; established travelers return to their saved workspace. */
export default function HomePage() {
  const [session, setSession] = useState(getSession);
  const [destination, setDestination] = useState(null);
  const [failed, setFailed] = useState(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const current = () => !controller.signal.aborted && isCurrentSession(session);
    setDestination(null);
    setFailed(null);
    const changed = () => {
      if (!isCurrentSession(session)) controller.abort();
      setSession(getSession());
      setDestination(null);
    };
    window.addEventListener('auth-changed', changed);
    if (
      !session.owner ||
      ['signin-required', 'signed-out'].includes(session.status) ||
      (!session.accessToken && !session.refreshToken)
    )
      setDestination('/plan');
    else {
      const load = async () => {
        let data;
        try {
          data = await initializeUserData(session.accessToken);
        } catch {
          if (current()) setFailed('owned');
          return;
        }
        if (!current()) return;
        if (!data) {
          setFailed('owned');
          return;
        }
        if (data.UserData.chatlogs.chatdata.some((trip) => trip.route)) {
          setDestination('/trips');
          return;
        }
        // Only an authenticated traveler without an owned route needs this
        // bounded private read. An outage is not evidence of an empty account.
        try {
          const rows = await listSharedTrips(controller.signal);
          if (!current()) return;
          if (!Array.isArray(rows)) throw new Error('Unavailable shared-trip list');
          setDestination(rows.length ? '/shared-trips' : '/plan');
        } catch {
          if (current()) setFailed('shared');
        }
      };
      void load();
    }
    return () => {
      controller.abort();
      window.removeEventListener('auth-changed', changed);
    };
  }, [session, attempt]);
  if (destination && isCurrentSession(session)) return <Navigate to={destination} replace />;
  return (
    <DesignFrame className="home-page">
      <main className="rt-stack">
        <p role={failed ? 'alert' : 'status'}>
          {failed
            ? session.status === 'unavailable'
              ? 'Session renewal is temporarily unavailable.'
              : failed === 'shared'
                ? 'Shared trips could not be checked. Retry or open Shared trips.'
                : 'Your saved trips could not be checked.'
            : 'Opening your trip planner…'}
        </p>
        {failed === 'shared' && (
          <Link className="rt-button rt-button--secondary" to="/shared-trips">
            Open shared trips
          </Link>
        )}
        {failed && <ActionButton onClick={() => setAttempt((old) => old + 1)}>Retry</ActionButton>}
      </main>
    </DesignFrame>
  );
}
