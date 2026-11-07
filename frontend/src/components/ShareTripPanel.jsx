import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton, Field, Sheet } from '../design';
import { getSession, isCurrentSession } from '../services/session';
import { useSessionStatus } from '../services/useSessionStatus';
import {
  changeSharing,
  createShareLink,
  getSharing,
  shareLinkUrl,
  sharingError,
} from '../services/tripSharing';
import '../pages/SharedTripPage/Sharing.css';

export default function ShareTripPanel({ trip }) {
  const session = useSessionStatus();
  const [record, setRecord] = useState(null);
  const [link, setLink] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const identity = `${session.owner}:${trip.chatId}:${trip.agentChatId}`;
  const status = record?.identity === identity ? record.data : null;
  useEffect(() => {
    const controller = new AbortController();
    const started = getSession();
    setRecord(null);
    setLink('');
    setError('');
    setMessage('');
    getSharing({ chatId: trip.chatId }, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted && isCurrentSession(started)) setRecord({ identity, data });
      })
      .catch((failure) => {
        if (!controller.signal.aborted && isCurrentSession(started))
          setError(sharingError(failure));
      });
    return () => controller.abort();
  }, [identity, trip.chatId, attempt]); // A link is tied to the saved trip identity, never to an account email.

  const act = async (action, memberId) => {
    if (busy) return;
    const started = getSession();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const data =
        action === 'create'
          ? await createShareLink(trip)
          : await changeSharing(trip, status.share_id, action, memberId);
      if (!isCurrentSession(started)) return;
      setRecord({ identity, data });
      if (action === 'create') setLink(shareLinkUrl(data.token));
      else setLink('');
      setMessage(
        action === 'create'
          ? 'New read-only link created. Older links no longer work.'
          : action === 'link'
            ? 'Link stopped. Connected accounts still have access.'
            : action === 'member'
              ? 'Account connection removed and link stopped. Other connected accounts keep access.'
              : 'All sharing stopped.'
      );
    } catch (failure) {
      if (isCurrentSession(started)) setError(sharingError(failure));
    } finally {
      if (isCurrentSession(started)) setBusy(false);
    }
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setMessage('Link copied. Send it only to people you want to view this trip.');
    } catch {
      setMessage('Select and copy the link from the field.');
    }
  };
  return (
    <Sheet aria-label="Trip sharing">
      <details className="trip-sharing-details">
        <summary className="rt-title">Share this trip</summary>
        <div className="rt-stack">
          <p className="rt-copy">
            Anyone with the link can view your route, trip addresses, dates and schedule for 30
            days, and connect a signed-in account for read-only access. Your private preferences,
            visit history and live location are excluded.
          </p>
          {error && (
            <p role="alert" className="rt-copy">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="rt-copy">
              {message}
            </p>
          )}
          {!status && !error && <p role="status">Loading sharing access…</p>}
          {error && (
            <ActionButton
              variant="secondary"
              disabled={busy}
              onClick={() => setAttempt((v) => v + 1)}
            >
              Reload sharing access
            </ActionButton>
          )}
          {status && (
            <>
              <ActionButton
                variant="secondary"
                disabled={busy}
                onClick={() => setAttempt((value) => value + 1)}
              >
                Refresh sharing access
              </ActionButton>
              <ActionButton disabled={busy || !trip.savedRevision} onClick={() => act('create')}>
                {status.link_enabled ? 'Replace sharing link' : 'Create sharing link'}
              </ActionButton>
              {!trip.savedRevision && (
                <p className="rt-copy">Reload this saved trip before creating a link.</p>
              )}
              {status.link_enabled && (
                <p className="rt-caption">
                  Link expires {new Date(status.link_expires_at).toLocaleDateString()}. Replacing it
                  keeps connected accounts.
                </p>
              )}
              {link && (
                <>
                  <Field
                    label="Read-only sharing link"
                    readOnly
                    value={link}
                    onFocus={(event) => event.target.select()}
                  />
                  <ActionButton variant="secondary" onClick={copy}>
                    Copy sharing link
                  </ActionButton>
                </>
              )}
              {status.link_enabled && (
                <ActionButton variant="secondary" disabled={busy} onClick={() => act('link')}>
                  Stop link
                </ActionButton>
              )}
              <h3 className="rt-title">Connected accounts</h3>
              <p className="rt-caption">
                Names below are chosen by each traveler. Stopping a link keeps these accounts
                connected; remove them or stop all sharing. Removing one connection also stops the
                current link; other connected accounts keep access.
              </p>
              {!status.members.length && <p className="rt-copy">No connected accounts.</p>}
              <ul className="sharing-list">
                {status.members.map((member) => (
                  <li key={member.id}>
                    <span>
                      {member.display_name} · {new Date(member.connected_at).toLocaleDateString()}
                    </span>
                    <ActionButton
                      variant="secondary"
                      disabled={busy}
                      onClick={() => act('member', member.id)}
                      aria-label={`Remove connection for ${member.display_name} and stop link`}
                    >
                      Remove connection and stop link
                    </ActionButton>
                  </li>
                ))}
              </ul>
              {status.share_id && (
                <ActionButton variant="secondary" disabled={busy} onClick={() => act('all')}>
                  Stop all sharing
                </ActionButton>
              )}
            </>
          )}
        </div>
      </details>
    </Sheet>
  );
}
ShareTripPanel.propTypes = { trip: PropTypes.object.isRequired };
