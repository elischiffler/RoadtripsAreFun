import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ActionButton, DesignFrame, Sheet } from '../../design';
import { getSession, isCurrentSession } from '../../services/session';
import { useSessionStatus } from '../../services/useSessionStatus';
import { listSharedTrips, sharingError } from '../../services/tripSharing';
import './Sharing.css';

export default function SharedTripsPage() {
  const session = useSessionStatus();
  const [record, setRecord] = useState(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const rows = record?.owner === session.owner ? record.rows : null;
  useEffect(() => {
    const started = getSession();
    const controller = new AbortController();
    setRecord(null);
    setError('');
    listSharedTrips(controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted && isCurrentSession(started))
          setRecord({ owner: started.owner, rows });
      })
      .catch((failure) => {
        if (!controller.signal.aborted && isCurrentSession(started))
          setError(sharingError(failure));
      });
    return () => controller.abort();
  }, [session.owner, attempt]);
  return (
    <DesignFrame>
      <h1 className="rt-display">Shared with me</h1>
      <p className="rt-copy">
        Read-only connections to the owner’s trip. Your saved trips stay separate.
      </p>
      <Link to="/trips" className="sharing-link">
        Your saved trips
      </Link>
      {error && <p role="alert">{error}</p>}
      {!rows && !error && <p role="status">Loading connected trips…</p>}
      <ActionButton variant="secondary" onClick={() => setAttempt((v) => v + 1)}>
        Refresh connections
      </ActionButton>
      {rows?.length === 0 && (
        <p className="rt-copy">
          No connected trips yet. Open a sharing link and choose Connect my account.
        </p>
      )}
      <ul className="sharing-list">
        {rows?.map((trip) => (
          <li key={trip.share_id}>
            <Sheet>
              <h2 className="rt-title">{trip.title}</h2>
              <Link className="sharing-link" to={`/shared-trips/${trip.share_id}`}>
                View shared trip
              </Link>
            </Sheet>
          </li>
        ))}
      </ul>
    </DesignFrame>
  );
}
