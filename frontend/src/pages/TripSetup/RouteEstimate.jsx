import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton, ChoiceGroup, QuestionGroup } from '../../design';
import {
  estimateStructuredRoute,
  plannerError,
  resolveTripLocation,
} from '../../services/tripPlanner';
import { getSession, isCurrentSession } from '../../services/session';
import Map from '../../components/Map';
import './ConnectedPlanning.css';

/** Read-only driving estimate; ambiguity is resolved explicitly before routing. */
export default function RouteEstimate({ start, destination }) {
  const [candidates, setCandidates] = useState(null);
  const [selected, setSelected] = useState({ origin: '', destination: '' });
  const [estimate, setEstimate] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(null);
  useEffect(() => {
    request.current?.abort();
    request.current = null;
    setCandidates(null);
    setEstimate(null);
    setBusy(false);
    setError('');
    const mountedSession = getSession();
    const changed = () => {
      if (isCurrentSession(mountedSession)) return;
      request.current?.abort();
      request.current = null;
      setCandidates(null);
      setEstimate(null);
      setBusy(false);
    };
    window.addEventListener('auth-changed', changed);
    return () => {
      request.current?.abort();
      request.current = null;
      window.removeEventListener('auth-changed', changed);
    };
  }, [start, destination]);

  const run = async (confirmed) => {
    request.current?.abort();
    const controller = new AbortController();
    const session = getSession();
    request.current = controller;
    const current = () =>
      request.current === controller && !controller.signal.aborted && isCurrentSession(session);
    setBusy(true);
    setError('');
    setEstimate(null);
    try {
      let places = candidates;
      let choices = selected;
      if (!confirmed) {
        const [origin, target] = await Promise.all([
          resolveTripLocation(start.trim(), controller.signal),
          resolveTripLocation(destination.trim(), controller.signal),
        ]);
        if (!current()) return;
        places = { origin, destination: target };
        choices = {
          origin: origin.length === 1 ? '0' : '',
          destination: target.length === 1 ? '0' : '',
        };
        setCandidates(places);
        setSelected(choices);
        if (!choices.origin || !choices.destination) return;
      }
      if (!places || choices.origin === '' || choices.destination === '') return;
      const result = await estimateStructuredRoute(
        places.origin[Number(choices.origin)],
        places.destination[Number(choices.destination)],
        controller.signal
      );
      if (current()) setEstimate(result);
    } catch (failure) {
      if (current()) setError(plannerError(failure));
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  };
  return (
    <QuestionGroup legend="Preview route">
      <ActionButton
        variant="secondary"
        disabled={busy || !start.trim() || !destination.trim()}
        onClick={() => run(false)}
      >
        {busy ? 'Checking the drive…' : 'Estimate driving time'}
      </ActionButton>
      {candidates && !estimate && (
        <div className="rt-stack">
          {['origin', 'destination'].map((field) => (
            <ChoiceGroup
              key={field}
              legend={field === 'origin' ? 'Estimate starting location' : 'Estimate destination'}
              value={selected[field]}
              disabled={busy}
              onChange={(value) => setSelected((old) => ({ ...old, [field]: value }))}
              options={candidates[field].map((place, index) => ({
                value: String(index),
                label: place.address,
              }))}
            />
          ))}
          <ActionButton
            variant="secondary"
            disabled={busy || selected.origin === '' || selected.destination === ''}
            onClick={() => run(true)}
          >
            Use these locations for estimate
          </ActionButton>
        </div>
      )}
      {estimate && (
        <div className="connected-estimate" role="status">
          <p className="rt-copy">
            {candidates.origin[Number(selected.origin)].address} →{' '}
            {candidates.destination[Number(selected.destination)].address}
          </p>
          <p className="rt-caption">Edit Start or Destination above to change this route.</p>
          {estimate.geometry?.coordinates?.length > 1 && (
            <div className="setup-estimate-map" aria-label="Estimated route map">
              <Map
                UserChatData={{
                  route: estimate,
                  startConfirmed: candidates.origin[Number(selected.origin)],
                  endConfirmed: candidates.destination[Number(selected.destination)],
                }}
              />
            </div>
          )}
          <p className="rt-title">About {(estimate.duration / 3600).toFixed(1)} hours driving</p>
          <p className="rt-copy">
            {(estimate.distance / 1609.344).toFixed(1)} miles before adding stops
          </p>
          <p className="rt-caption">
            Driving only. Visits, meals and overnight stays add time. You’ll confirm your trip
            locations again before planning.
          </p>
        </div>
      )}
      {error && (
        <p role="alert" className="connected-error">
          {error}
        </p>
      )}
    </QuestionGroup>
  );
}
RouteEstimate.propTypes = {
  start: PropTypes.string.isRequired,
  destination: PropTypes.string.isRequired,
};
