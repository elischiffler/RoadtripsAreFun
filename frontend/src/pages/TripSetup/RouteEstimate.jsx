import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton, ChoiceGroup } from '../../design';
import {
  estimateStructuredRoute,
  plannerError,
  resolveTripLocation,
} from '../../services/tripPlanner';
import { getSession, isCurrentSession } from '../../services/session';
import OnboardingMap from './OnboardingMap';
import useCatalogPreparation from './useCatalogPreparation';
import './ConnectedPlanning.css';

/** User-triggered road preparation, then admitted database ideas. No AI runs here. */
const RouteEstimate = forwardRef(function RouteEstimate(
  { start, destination, draft, stage = 0, onPrepared },
  ref
) {
  const [candidates, setCandidates] = useState(null);
  const [selected, setSelected] = useState({ origin: '', destination: '' });
  const [prepared, setPrepared] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(null);
  const notify = useRef(onPrepared);
  notify.current = onPrepared;
  const queryKey = JSON.stringify([start.trim(), destination.trim()]);

  useEffect(() => {
    request.current?.abort();
    request.current = null;
    setCandidates(null);
    setPrepared(null);
    setBusy(false);
    setError('');
    notify.current?.(null);
    const session = getSession();
    const changed = () => {
      if (isCurrentSession(session)) return;
      request.current?.abort();
      request.current = null;
      setCandidates(null);
      setPrepared(null);
      setBusy(false);
      setError('');
      notify.current?.(null);
    };
    window.addEventListener('auth-changed', changed);
    return () => {
      request.current?.abort();
      request.current = null;
      window.removeEventListener('auth-changed', changed);
    };
  }, [queryKey]);

  const currentData =
    prepared?.queryKey === queryKey && isCurrentSession(prepared.session) ? prepared : null;
  const catalog = useCatalogPreparation(currentData?.initialRoute, currentData?.cacheKey, draft);

  const run = async (confirmed = false) => {
    if (!confirmed && currentData) return { ok: true, ...currentData };
    request.current?.abort();
    const controller = new AbortController(),
      session = getSession();
    request.current = controller;
    const current = () =>
      request.current === controller && !controller.signal.aborted && isCurrentSession(session);
    setBusy(true);
    setError('');
    try {
      let places = candidates?.queryKey === queryKey ? candidates : null;
      let choices = selected;
      if (!places) {
        const [origin, target] = await Promise.all([
          resolveTripLocation(start.trim(), controller.signal),
          resolveTripLocation(destination.trim(), controller.signal),
        ]);
        if (!current()) return { ok: false };
        places = { origin, destination: target, queryKey };
        choices = {
          origin: origin.length === 1 ? '0' : '',
          destination: target.length === 1 ? '0' : '',
        };
        setCandidates(places);
        setSelected(choices);
      }
      if (choices.origin === '' || choices.destination === '')
        return { ok: false, needsLocations: true };
      const origin = places.origin[Number(choices.origin)],
        target = places.destination[Number(choices.destination)];
      const initialRoute = await estimateStructuredRoute(origin, target, controller.signal);
      if (!current()) return { ok: false };
      const data = {
        queryKey,
        cacheKey: JSON.stringify([queryKey, initialRoute.geometry]),
        origin: { ...origin, confirmed },
        destination: { ...target, confirmed },
        initialRoute,
        session: { owner: session.owner, generation: session.generation },
      };
      setPrepared(data);
      notify.current?.(data);
      return { ok: true, ...data };
    } catch (failure) {
      if (current()) setError(plannerError(failure));
      return { ok: false };
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  };
  useImperativeHandle(ref, () => ({
    prepare: async () => {
      const value = await run(false);
      if (!value?.ok || !isCurrentSession(value.session)) return value;
      const confirmed = {
        ...value,
        origin: { ...value.origin, confirmed: true },
        destination: { ...value.destination, confirmed: true },
      };
      setPrepared(confirmed);
      notify.current?.(confirmed);
      return confirmed;
    },
  }));

  return (
    <div className="setup-route-preparation">
      <OnboardingMap
        origin={currentData?.origin ?? { address: start }}
        destination={currentData?.destination ?? { address: destination }}
        route={currentData?.initialRoute}
        ideas={catalog.places}
        stayAreas={catalog.areas}
        stage={stage}
        phase={busy ? 'checking' : catalog.status === 'loading' ? 'preparing' : 'draft'}
      />
      {stage === 0 && (
        <ActionButton
          variant="secondary"
          disabled={busy || !start.trim() || !destination.trim()}
          onClick={() => run(false)}
        >
          {busy ? 'Checking places…' : 'Estimate driving time'}
        </ActionButton>
      )}
      {stage === 0 && candidates?.queryKey === queryKey && !currentData && (
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
      {currentData && (
        <p className="rt-caption">
          About {(currentData.initialRoute.duration / 3600).toFixed(1)} hours driving · driving
          only, before stops and meals.
        </p>
      )}
      {catalog.places.length > 0 && (
        <p className="rt-caption">
          Catalog ideas may be missing. Opening hours for your travel date are checked with trip
          options.
        </p>
      )}
      {catalog.status === 'loading' && (
        <p className="rt-caption" role="status">
          Preparing catalog ideas · {catalog.sections} of 6 route sections checked…
        </p>
      )}
      {['partial', 'unavailable'].includes(catalog.status) && (
        <p className="rt-caption" role="status">
          Some catalog ideas could not be checked. You can continue planning.
        </p>
      )}
      {catalog.areas.length > 0 && (
        <p className="rt-caption">
          Stay areas use approximate departure-clock timing, driving hours and meal allowances.
          Visits, detours and local clocks may move them. No hotel availability checked.
        </p>
      )}
      {busy && (
        <p role="status" className="rt-caption">
          Preparing the road preview.
        </p>
      )}
      {error && (
        <p role="alert" className="connected-error">
          {error}
        </p>
      )}
    </div>
  );
});
RouteEstimate.propTypes = {
  start: PropTypes.string.isRequired,
  destination: PropTypes.string.isRequired,
  draft: PropTypes.object,
  stage: PropTypes.number,
  onPrepared: PropTypes.func,
};
export default RouteEstimate;
