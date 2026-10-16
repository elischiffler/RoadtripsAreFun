import { useContext, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChatData, Data, UserDataContext } from '../../states/UserDataContext';
import { initializeUserData, ensureChatCreated, updateUserData } from '../../services/savedTrips';
import { getSession, isCurrentSession } from '../../services/session';
import {
  resolveTripLocation,
  planStructuredRoute,
  planStructuredItinerary,
  plannerError,
  structuredTripInputs,
} from '../../services/tripPlanner';
import TripSetup from './TripSetup';
import PreferenceProfile from './PreferenceProfile';

export default function TripSetupPage() {
  const { setUserData, setChats } = useContext(UserDataContext);
  const [loaded, setLoaded] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [proposal, setProposal] = useState(null);
  const [selections, setSelections] = useState({ origin: 0, destination: 0 });
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const request = useRef(null);
  const heading = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const session = getSession();
    setLoadError(false);
    initializeUserData(session.accessToken).then((data) => {
      if (cancelled || !isCurrentSession(session)) return;
      if (!data) setLoadError(true);
      else setLoaded(data);
    });
    return () => {
      cancelled = true;
      request.current?.abort();
      request.current = null;
    };
  }, [loadAttempt]);

  useEffect(() => {
    heading.current?.focus();
  }, [proposal, result, error]);

  const locate = async ({ draft }) => {
    const session = getSession();
    const controller = new AbortController();
    request.current = controller;
    try {
      const [origin, destination] = await Promise.all([
        resolveTripLocation(draft.start.trim(), controller.signal),
        resolveTripLocation(draft.destination.trim(), controller.signal),
      ]);
      if (!isCurrentSession(session) || controller.signal.aborted)
        return { error: 'Session changed. Please sign in again.' };
      setSelections({ origin: 0, destination: 0 });
      setProposal({ draft, origin, destination });
      setError('');
      return { ok: true };
    } catch (failure) {
      return {
        error: failure.message && !failure.response ? failure.message : plannerError(failure),
      };
    } finally {
      if (request.current === controller) request.current = null;
    }
  };

  const save = async (current, session) => {
    if (!isCurrentSession(session)) return false;
    const logs = loaded.UserData.chatlogs;
    const records = [
      ...loaded.chats.filter((item) => item.id !== current.snapshot.chatId),
      current.record,
    ];
    const saved = current.persisted
      ? await updateUserData(session.accessToken, current.snapshot, records, logs)
      : await ensureChatCreated(session.accessToken, current.snapshot, records, logs);
    if (!isCurrentSession(session)) return false;
    if (!saved) return false;
    const index = logs.chatdata.findIndex((item) => item.chatId === current.snapshot.chatId);
    if (index < 0) logs.addChatData(current.snapshot);
    else logs.chatdata[index] = current.snapshot;
    logs.currentId = current.snapshot.chatId;
    sessionStorage.setItem('selectedChatId', String(logs.currentId));
    setUserData(new Data(logs));
    setChats(records);
    setLoaded({ UserData: new Data(logs), chats: records });
    return true;
  };

  const plan = async () => {
    if (busy || !proposal) return;
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    try {
      const origin = proposal.origin[selections.origin],
        destination = proposal.destination[selections.destination];
      const route = await planStructuredRoute(
        proposal.draft,
        origin,
        destination,
        controller.signal
      );
      if (!isCurrentSession(session) || controller.signal.aborted) return;
      // IDs are allocated only after owner-scoped saved records have loaded.
      const id = Math.max(0, ...loaded.UserData.chatlogs.chatdata.map((item) => item.chatId)) + 1;
      const snapshot = new ChatData(id);
      Object.assign(snapshot, {
        agentChatId: crypto.randomUUID(),
        route,
        itinerary: null,
        startConfirmed: origin,
        endConfirmed: destination,
        startCoords: [origin.latitude, origin.longitude],
        endCoords: [destination.latitude, destination.longitude],
        stops: Number(proposal.draft.stops),
        hotelBudget: Number(proposal.draft.budget),
        carDetails: [proposal.draft.year, proposal.draft.make, proposal.draft.model],
        isComplete: false,
        tripProfile: {
          ...structuredTripInputs(proposal.draft),
          start_address: origin.address,
          destination_address: destination.address,
          start_timezone: route.start_timezone,
          car_status: proposal.draft.carStatus,
          departure_time: proposal.draft.time,
          start_date: route.departure_time,
          start_coords: [origin.latitude, origin.longitude],
          destination_coords: [destination.latitude, destination.longitude],
          ...(proposal.draft.carStatus === 'provided'
            ? {
                car: {
                  year: Number(proposal.draft.year),
                  make: proposal.draft.make,
                  model: proposal.draft.model,
                },
              }
            : {}),
        },
      });
      const current = {
        route,
        snapshot,
        record: { id, title: origin.address + ' → ' + destination.address, messages: [] },
        weights: structuredTripInputs(proposal.draft).persona_weights,
        saved: false,
        persisted: false,
      };
      try {
        const itinerary = await planStructuredItinerary(route, controller.signal);
        if (!isCurrentSession(session) || controller.signal.aborted) return;
        current.itinerary = itinerary;
        snapshot.itinerary = itinerary;
        snapshot.isComplete = true;
      } catch (failure) {
        if (controller.signal.aborted || !isCurrentSession(session)) return;
        current.itineraryError = plannerError(failure);
      }
      setSaving(true);
      current.saved = await save(current, session);
      current.persisted = current.persisted || current.saved;
      setSaving(false);
      if (!isCurrentSession(session) || controller.signal.aborted) return;
      setResult(current);
      if (!current.saved)
        setError('The route is available, but it could not be saved. Retry saving before leaving.');
    } catch (failure) {
      if (isCurrentSession(session) && !controller.signal.aborted) setError(plannerError(failure));
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
        setSaving(false);
      }
    }
  };

  const retry = async (itineraryOnly) => {
    if (busy || !result) return;
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    try {
      const next = { ...result, snapshot: { ...result.snapshot } };
      if (itineraryOnly) {
        next.itinerary = await planStructuredItinerary(result.route, controller.signal);
        next.snapshot.itinerary = next.itinerary;
        next.snapshot.isComplete = true;
        next.itineraryError = '';
      }
      if (!isCurrentSession(session) || controller.signal.aborted) return;
      setSaving(true);
      next.saved = await save(next, session);
      next.persisted = next.persisted || next.saved;
      setSaving(false);
      if (!isCurrentSession(session) || controller.signal.aborted) return;
      setResult(next);
      if (!next.saved) setError('This trip could not be saved. Please retry before leaving.');
    } catch (failure) {
      if (!controller.signal.aborted && isCurrentSession(session)) setError(plannerError(failure));
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
        setSaving(false);
      }
    }
  };

  if (loadError)
    return (
      <main className="trip-setup">
        <div role="alert">
          <h1>Saved trips could not be loaded.</h1>
          <p>Retry before creating a new trip.</p>
          <button className="setup-primary" onClick={() => setLoadAttempt((value) => value + 1)}>
            Retry loading trips
          </button>
        </div>
      </main>
    );
  if (!loaded)
    return (
      <main className="trip-setup">
        <p role="status">Loading your saved trips…</p>
      </main>
    );
  if (!proposal) return <TripSetup onSubmit={locate} />;

  return (
    <main className="trip-setup">
      <div className="setup-wayfinding">
        <Link to="/">Home</Link>
        <Link to="/trips">Saved trips</Link>
        <Link to="/studio">AI Studio</Link>
      </div>
      <section className="setup-card setup-section">
        <h1 ref={heading} tabIndex={-1}>
          {result ? 'Your trip' : 'Confirm your locations'}
        </h1>
        {error && (
          <p role="alert" className="setup-error-summary">
            {error}
          </p>
        )}
        {!result && (
          <>
            <p>Choose the addresses you mean. Planning starts only when you confirm them below.</p>
            {['origin', 'destination'].map((field) => (
              <fieldset className="setup-room" key={field} disabled={busy}>
                <legend>{field === 'origin' ? 'Starting location' : 'Destination'}</legend>
                {proposal[field].map((candidate, index) => (
                  <label className="setup-choice" key={candidate.address + index}>
                    <input
                      type="radio"
                      name={field}
                      checked={selections[field] === index}
                      onChange={() => setSelections((old) => ({ ...old, [field]: index }))}
                    />
                    {candidate.address}
                  </label>
                ))}
              </fieldset>
            ))}
            <p className="setup-hint">
              Departure is {proposal.draft.date} at {proposal.draft.time}, local to your starting
              location. The planning service checks the final schedule. Route planning uses AI place
              ratings and live road and hotel providers.
            </p>
            <button
              className="setup-secondary"
              disabled={busy}
              onClick={() => {
                setProposal(null);
                setError('');
              }}
            >
              Edit answers
            </button>{' '}
            <button className="setup-primary" disabled={busy} onClick={plan}>
              Confirm locations and plan route
            </button>
          </>
        )}
        {busy && (
          <div role="status">
            <p>Working on your trip. Provider checks can take several minutes.</p>
            <button
              className="setup-secondary"
              disabled={saving}
              onClick={() => {
                request.current?.abort();
                request.current = null;
                setBusy(false);
                setError(
                  'Stopped waiting. Your draft is kept. A request already received by the service may still finish.'
                );
              }}
            >
              Stop waiting
            </button>
          </div>
        )}
        {result && (
          <>
            <p role="status">{result.saved ? 'Trip saved.' : 'Trip is not saved yet.'}</p>
            <dl className="setup-review">
              <dt>Driving distance</dt>
              <dd>{(result.route.distance / 1609.344).toFixed(1)} miles</dd>
              <dt>Driving time</dt>
              <dd>{(result.route.duration / 3600).toFixed(1)} hours</dd>
              <dt>Quoted hotel total</dt>
              <dd>
                {Number.isFinite(result.route.cost)
                  ? '$' + result.route.cost.toFixed(2)
                  : 'Unavailable'}
              </dd>
            </dl>
            <p className="setup-hint">
              Driving excludes visits and overnight stays. Hotel quotes exclude fuel, food and
              tickets and do not guarantee booking availability.
            </p>
            {(result.route.warnings ?? []).map((warning, index) => (
              <p role="note" key={index}>
                {warning}
              </p>
            ))}
            <PreferenceProfile weights={result.weights} label="Interests sent to the planner" />
            <button
              type="button"
              className="setup-secondary"
              disabled={busy}
              onClick={() => {
                setResult(null);
                setProposal(null);
                setError('');
              }}
            >
              Edit draft for another trip
            </button>
            {result.itineraryError && (
              <div role="alert">
                <p>
                  The route is available, but the itinerary could not finish.{' '}
                  {result.itineraryError}
                </p>
                <button className="setup-secondary" disabled={busy} onClick={() => retry(true)}>
                  Retry itinerary
                </button>
              </div>
            )}
            {!result.saved && (
              <button className="setup-primary" disabled={busy} onClick={() => retry(false)}>
                Retry saving trip
              </button>
            )}
            {result.saved && (
              <div className="setup-inline-actions">
                <Link to="/map">View map</Link>
                {result.itinerary && <Link to="/itinerary">View itinerary</Link>}
                <Link to="/trips">Open saved trips</Link>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
