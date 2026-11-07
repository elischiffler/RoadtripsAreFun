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
import { ActionButton, ChoiceGroup, DesignFrame, Sheet, StageProgress } from '../../design';
import { preferenceProfiles, STEPS } from './setupModel';
import { advancePlanningProgress, newPlanningProgress } from '../../services/tripPlanningProgress';
import RouteEstimate from './RouteEstimate';
import PlanningProgress from './PlanningProgress';
import './ConnectedPlanning.css';

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
  const [progress, setProgress] = useState(newPlanningProgress);
  const report = (event) => setProgress((old) => advancePlanningProgress(old, event));
  const request = useRef(null);
  const heading = useRef(null);
  const isActive = (controller, session) =>
    request.current === controller && !controller.signal.aborted && isCurrentSession(session);

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
      if (!isActive(controller, session))
        return { error: 'Session changed. Please sign in again.' };
      setSelections({
        origin: origin.length === 1 ? 0 : -1,
        destination: destination.length === 1 ? 0 : -1,
      });
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

  const save = async (current, session, controller) => {
    if (!isActive(controller, session) || !current.itinerary || !current.snapshot.isComplete)
      return false;
    const logs = loaded.UserData.chatlogs;
    const records = [
      ...loaded.chats.filter((item) => item.id !== current.snapshot.chatId),
      current.record,
    ];
    const saved = current.persisted
      ? await updateUserData(session.accessToken, current.snapshot, records, logs)
      : await ensureChatCreated(session.accessToken, current.snapshot, records, logs);
    if (!isActive(controller, session)) return false;
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
    if (selections.origin < 0 || selections.destination < 0) {
      setError('Choose both confirmed locations before planning.');
      return;
    }
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    setProgress(
      advancePlanningProgress(newPlanningProgress(), {
        type: 'progress',
        stage: 'details.confirmed',
        state: 'completed',
      })
    );
    try {
      const origin = proposal.origin[selections.origin],
        destination = proposal.destination[selections.destination];
      const route = await planStructuredRoute(
        proposal.draft,
        origin,
        destination,
        controller.signal,
        {
          reserveMealSlots: true,
          onProgress: (event) => {
            if (isActive(controller, session)) report(event);
          },
        }
      );
      if (!isActive(controller, session)) return;
      report({ type: 'progress', stage: 'route.ready', state: 'completed' });
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
        // Preserve fractional targets in tripProfile; the legacy hotelBudget slot is integer-only.
        carDetails: [proposal.draft.year, proposal.draft.make, proposal.draft.model],
        isComplete: false,
        tripProfile: {
          ...structuredTripInputs(proposal.draft),
          reserve_meal_slots: true,
          preference_profiles: preferenceProfiles(proposal.draft),
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
        const itinerary = await planStructuredItinerary(route, controller.signal, {
          includeMealSlots: true,
        });
        if (!isActive(controller, session)) return;
        current.itinerary = itinerary;
        snapshot.itinerary = itinerary;
        snapshot.isComplete = true;
        report({ type: 'progress', stage: 'itinerary.ready', state: 'completed' });
      } catch (failure) {
        if (!isActive(controller, session)) return;
        current.itineraryError = plannerError(failure);
        report({ type: 'failed' });
      }
      if (!current.itinerary) {
        setResult(current);
        return;
      }
      setSaving(true);
      current.saved = await save(current, session, controller);
      if (!isActive(controller, session)) return;
      current.persisted = current.persisted || current.saved;
      report(
        current.saved
          ? { type: 'progress', stage: 'trip.saved', state: 'completed' }
          : { type: 'failed' }
      );
      setSaving(false);
      if (!isActive(controller, session)) return;
      setResult(current);
      if (!current.saved)
        setError('The route is available, but it could not be saved. Retry saving before leaving.');
    } catch (failure) {
      if (isActive(controller, session)) {
        setError(plannerError(failure));
        report({ type: 'failed' });
      }
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
        setSaving(false);
      }
    }
  };

  const retry = async (itineraryOnly) => {
    if (busy || !result || (!itineraryOnly && !result.itinerary)) return;
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    report({ type: 'resume' });
    try {
      const next = { ...result, snapshot: { ...result.snapshot } };
      if (itineraryOnly) {
        const itinerary = await planStructuredItinerary(result.route, controller.signal, {
          includeMealSlots: true,
        });
        if (!isActive(controller, session)) return;
        next.itinerary = itinerary;
        next.snapshot.itinerary = itinerary;
        next.snapshot.isComplete = true;
        next.itineraryError = '';
        report({ type: 'progress', stage: 'itinerary.ready', state: 'completed' });
      }
      if (!isActive(controller, session)) return;
      setSaving(true);
      next.saved = await save(next, session, controller);
      if (!isActive(controller, session)) return;
      next.persisted = next.persisted || next.saved;
      report(
        next.saved
          ? { type: 'progress', stage: 'trip.saved', state: 'completed' }
          : { type: 'failed' }
      );
      setSaving(false);
      if (!isActive(controller, session)) return;
      setResult(next);
      if (!next.saved) setError('This trip could not be saved. Please retry before leaving.');
    } catch (failure) {
      if (isActive(controller, session)) {
        setError(plannerError(failure));
        report({ type: 'failed' });
      }
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
        <DesignFrame className="setup-design">
          <Sheet aria-label="Saved trips unavailable">
            <div role="alert">
              <h1 className="rt-display">Saved trips could not be loaded.</h1>
              <p className="rt-copy">Retry before creating a new trip.</p>
            </div>
            <ActionButton onClick={() => setLoadAttempt((value) => value + 1)}>
              Retry loading trips
            </ActionButton>
          </Sheet>
        </DesignFrame>
      </main>
    );
  if (!loaded)
    return (
      <main className="trip-setup">
        <DesignFrame className="setup-design">
          <p role="status" className="rt-copy">
            Loading your saved trips…
          </p>
        </DesignFrame>
      </main>
    );
  if (!proposal)
    return (
      <TripSetup
        onSubmit={locate}
        renderEstimate={(draft) => (
          <RouteEstimate start={draft.start} destination={draft.destination} />
        )}
      />
    );

  return (
    <main className="trip-setup">
      <DesignFrame className="setup-design">
        <nav className="connected-links" aria-label="Trip navigation">
          <Link to="/">Home</Link>
          <Link to="/trips">Saved trips</Link>
        </nav>
        {!result && (
          <StageProgress
            stages={STEPS.map((label, index) => ({ id: String(index), label }))}
            currentId="4"
            completedIds={['0', '1', '2', '3']}
          />
        )}
        <Sheet aria-label={result ? 'Your trip' : 'Review and confirm'}>
          {!result && <p className="rt-caption">Review · Step 5 of 5</p>}
          <h1 ref={heading} tabIndex={-1} className="rt-display">
            {result ? 'Your trip' : 'Confirm your locations'}
          </h1>
          {error && (
            <p role="alert" className="connected-error">
              {error}
            </p>
          )}
          {!result && (
            <>
              <p className="rt-copy">
                Choose the addresses you mean. Planning starts only when you confirm them below.
              </p>
              {['origin', 'destination'].map((field) => (
                <ChoiceGroup
                  key={field}
                  legend={field === 'origin' ? 'Starting location' : 'Destination'}
                  disabled={busy}
                  value={selections[field] < 0 ? '' : String(selections[field])}
                  onChange={(value) => setSelections((old) => ({ ...old, [field]: Number(value) }))}
                  options={proposal[field].map((candidate, index) => ({
                    value: String(index),
                    label: candidate.address,
                  }))}
                />
              ))}
              <p className="rt-caption">
                Departure is {proposal.draft.date} at {proposal.draft.time}, local to your starting
                location. The planning service checks the final schedule. Route planning uses AI
                place ratings and live road and hotel providers.
              </p>
              <p className="rt-caption">
                Meal breaks are included when your trip spans breakfast, lunch or dinner: 30, 45 and
                60 minutes. No dining places are selected or booked. If the breaks cannot fit your
                driving and visit schedule, planning will explain the conflict.
              </p>
              <ActionButton
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setProposal(null);
                  setError('');
                  setProgress(newPlanningProgress());
                }}
              >
                Edit answers
              </ActionButton>
              <ActionButton
                disabled={busy || selections.origin < 0 || selections.destination < 0}
                onClick={plan}
              >
                Confirm locations and plan route
              </ActionButton>
            </>
          )}
          {progress.percent > 0 && <PlanningProgress progress={progress} />}
          {busy && (
            <div className="rt-stack">
              <p className="rt-caption">
                Working on your trip. Provider checks can take several minutes.
              </p>
              <ActionButton
                variant="secondary"
                disabled={saving}
                onClick={() => {
                  request.current?.abort();
                  request.current = null;
                  setBusy(false);
                  report({ type: 'failed' });
                  setError(
                    'Stopped waiting. Your draft is kept. A request already received by the service may still finish.'
                  );
                }}
              >
                Stop waiting
              </ActionButton>
            </div>
          )}
          {result && (
            <>
              <p role="status" className="rt-copy">
                {result.saved ? 'Trip saved.' : 'Trip is not saved yet.'}
              </p>
              <dl className="connected-summary">
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
              <p className="rt-caption">
                Driving excludes visits, meal breaks and overnight stays. Hotel quotes exclude fuel,
                food and tickets and do not guarantee booking availability.
              </p>
              {(result.route.warnings ?? []).map((warning, index) => (
                <p role="note" key={index} className="rt-caption">
                  {warning}
                </p>
              ))}
              <ActionButton
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setResult(null);
                  setProposal(null);
                  setError('');
                  setProgress(newPlanningProgress());
                }}
              >
                Edit draft for another trip
              </ActionButton>
              {result.itineraryError && (
                <div role="alert" className="rt-stack">
                  <p className="rt-copy">
                    The route is available, but the itinerary could not finish.{' '}
                    {result.itineraryError}
                  </p>
                  <ActionButton variant="secondary" disabled={busy} onClick={() => retry(true)}>
                    Retry itinerary
                  </ActionButton>
                </div>
              )}
              {!result.saved && result.itinerary && (
                <ActionButton disabled={busy} onClick={() => retry(false)}>
                  Retry saving trip
                </ActionButton>
              )}
              {result.saved && (
                <nav className="connected-links" aria-label="Open your trip">
                  <Link className="rt-button rt-button--secondary" to="/trip">
                    Open trip
                  </Link>
                  {result.itinerary && (
                    <Link className="rt-button rt-button--secondary" to="/itinerary">
                      View itinerary
                    </Link>
                  )}
                  <Link to="/trips">Open saved trips</Link>
                </nav>
              )}
            </>
          )}
        </Sheet>
      </DesignFrame>
    </main>
  );
}
