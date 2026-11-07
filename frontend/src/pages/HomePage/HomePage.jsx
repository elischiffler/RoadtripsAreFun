import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { ActionButton, DesignFrame } from '../../design';
import { initializeUserData } from '../../services/savedTrips';
import { getSession, isCurrentSession } from '../../services/session';

/** Enter planning directly; established travelers return to their saved workspace. */
export default function HomePage() {
  const [session, setSession] = useState(getSession);
  const [destination, setDestination] = useState(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setDestination(null);
    setFailed(false);
    const changed = () => {
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
    else
      initializeUserData(session.accessToken).then((data) => {
        if (!alive || !isCurrentSession(session)) return;
        if (!data) setFailed(true);
        else
          setDestination(
            data.UserData.chatlogs.chatdata.some((trip) => trip.route) ? '/trips' : '/plan'
          );
      });
    return () => {
      alive = false;
      window.removeEventListener('auth-changed', changed);
    };
  }, [session, attempt]);
  if (destination && isCurrentSession(session)) return <Navigate to={destination} replace />;
  return (
    <DesignFrame>
      <main className="rt-stack">
        <p role={failed ? 'alert' : 'status'}>
          {failed
            ? session.status === 'unavailable'
              ? 'Session renewal is temporarily unavailable.'
              : 'Your saved trips could not be checked.'
            : 'Opening your trip planner…'}
        </p>
        {failed && <ActionButton onClick={() => setAttempt((old) => old + 1)}>Retry</ActionButton>}
      </main>
    </DesignFrame>
  );
}
